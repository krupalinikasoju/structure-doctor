from typing import Dict, Any


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _yes(value):
    return str(value).strip().lower() == "yes"


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, float(value)))


def assess_risk(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Explainable preliminary screening engine.

    IMPORTANT:
    This is NOT a structural-strength calculation.
    It does NOT determine load-bearing capacity or certify safety.
    """

    score = 0
    reasons = []

    element = str(inputs.get("element", "Other / unknown"))
    crack_type = str(inputs.get("crack_type", "Auto / unknown"))
    width_mm = _safe_float(inputs.get("width_mm"), 0)
    detected = bool(inputs.get("detected", False))
    confidence = _safe_float(inputs.get("confidence"), 0)

    length_px = _safe_float(inputs.get("length_px"), 0)
    width_px = _safe_float(inputs.get("width_px"), 0)
    area_px = _safe_float(inputs.get("area_px"), 0)
    image_width = _safe_float(inputs.get("image_width"), 0)
    image_height = _safe_float(inputs.get("image_height"), 0)

    if not detected:
        return {
            "severity": "Low",
            "score": 0,
            "reasons": [
                "No sufficiently clear crack-like region was detected.",
                "Image quality, lighting, surface texture or viewpoint can affect detection.",
            ],
            "possible_causes": [
                "No sufficiently clear crack-like region was detected.",
                "The image may require better lighting, focus or viewing angle.",
            ],
            "safety_override": False,
            "visual_evidence": "No clear crack detected",
            "image_features_used": True,
        }

    image_area = max(image_width * image_height, 1.0)
    max_dimension = max(image_width, image_height, 1.0)

    area_ratio = _clamp(area_px / image_area)
    length_ratio = _clamp(length_px / max_dimension)
    width_ratio = _clamp(width_px / max_dimension)
    detection_quality = _clamp(confidence / 100.0)

    visual_points = 0

    if area_ratio >= 0.02:
        visual_points += 2
        reasons.append(
            "The detected crack-like region occupies a relatively large portion of the image."
        )
    elif area_ratio >= 0.005:
        visual_points += 1
        reasons.append(
            "The detected crack-like region has noticeable visual extent."
        )

    if length_ratio >= 0.45:
        visual_points += 2
        reasons.append(
            "The detected crack extends across a substantial portion of the image."
        )
    elif length_ratio >= 0.20:
        visual_points += 1
        reasons.append(
            "The detected crack has moderate visible length relative to the image."
        )

    if width_ratio >= 0.025:
        visual_points += 2
        reasons.append(
            "The detected region has a relatively broad visual width."
        )
    elif width_ratio >= 0.01:
        visual_points += 1
        reasons.append(
            "The detected region has measurable visual width."
        )

    score += min(visual_points, 5)

    reasons.append(
        "The crack-like region was identified using the OpenCV computer-vision pipeline."
    )

    if width_mm > 0:
        if width_mm >= 1.0:
            score += 3
            reasons.append(
                "The estimated visible crack width is relatively large based on the supplied image scale."
            )
        elif width_mm >= 0.5:
            score += 2
            reasons.append(
                "The estimated visible crack width is above a small surface-crack range based on the supplied image scale."
            )
        elif width_mm >= 0.3:
            score += 1
            reasons.append(
                "The estimated visible crack width warrants monitoring based on the supplied image scale."
            )

    if element == "Column":
        score += 2
        reasons.append(
            "The affected element is a column, so professional review is more important."
        )
    elif element == "Beam":
        score += 2
        reasons.append(
            "The affected element is a beam, so professional review is more important."
        )
    elif element == "Foundation":
        score += 2
        reasons.append(
            "Foundation cracking can be associated with movement or settlement."
        )
    elif element == "Slab":
        score += 1
        reasons.append(
            "The affected element is a slab."
        )

    if crack_type == "Diagonal":
        score += 2
        reasons.append(
            "Diagonal cracking can have multiple causes and deserves closer review."
        )
    elif crack_type == "Map-like":
        score += 1
        reasons.append(
            "Map-like cracking can be associated with surface or material deterioration."
        )
    elif crack_type == "Vertical":
        reasons.append(
            "The selected pattern is predominantly vertical."
        )
    elif crack_type == "Horizontal":
        reasons.append(
            "The selected pattern is predominantly horizontal."
        )

    if _yes(inputs.get("seepage")):
        score += 1
        reasons.append("Water seepage or dampness is present.")

    if _yes(inputs.get("rust")):
        score += 3
        reasons.append(
            "Visible rust/reinforcement is a significant deterioration indicator."
        )

    if _yes(inputs.get("progression")):
        score += 3
        reasons.append(
            "The user reports that the crack is increasing."
        )

    if _yes(inputs.get("event")):
        score += 2
        reasons.append(
            "A recent earthquake, impact or unusual event was reported."
        )

    if _yes(inputs.get("deformation")):
        score += 4
        reasons.append(
            "Visible deformation or displacement is reported."
        )

    if _yes(inputs.get("sound")):
        score += 2
        reasons.append(
            "An unusual hollow or loose area is reported."
        )

    safety_override = (
        _yes(inputs.get("deformation"))
        or (
            _yes(inputs.get("rust"))
            and element in {"Column", "Beam", "Foundation"}
        )
    )

    if safety_override or score >= 9:
        severity = "Critical"
    elif score >= 6:
        severity = "High"
    elif score >= 3:
        severity = "Moderate"
    else:
        severity = "Low"

    if area_ratio >= 0.02 or length_ratio >= 0.45:
        visual_evidence = (
            "Large visible crack extent relative to the uploaded image."
        )
    elif area_ratio >= 0.005 or length_ratio >= 0.20:
        visual_evidence = (
            "Moderate visible crack extent relative to the uploaded image."
        )
    else:
        visual_evidence = (
            "Limited visible crack extent relative to the uploaded image."
        )

    possible_causes = []

    if _yes(inputs.get("seepage")):
        possible_causes.append("Moisture-related deterioration")

    if crack_type in {"Vertical", "Horizontal", "Diagonal", "Random / irregular"}:
        possible_causes.append(
            "Shrinkage, thermal movement or material movement"
        )

    if crack_type == "Diagonal":
        possible_causes.append(
            "Settlement or structural movement — requires professional assessment to distinguish"
        )

    if _yes(inputs.get("event")):
        possible_causes.append(
            "Impact, seismic or event-related damage"
        )

    if _yes(inputs.get("rust")):
        possible_causes.append(
            "Possible reinforcement corrosion / concrete deterioration"
        )

    if crack_type == "Map-like":
        possible_causes.append(
            "Surface/material deterioration or shrinkage-related cracking"
        )

    if not possible_causes:
        possible_causes = [
            "Shrinkage or thermal movement",
            "Surface/material movement",
            "Moisture-related deterioration",
            "Other causes that cannot be confirmed from the image alone",
        ]

    possible_causes = list(dict.fromkeys(possible_causes))

    return {
        "severity": severity,
        "score": score,
        "reasons": reasons[:12],
        "possible_causes": possible_causes[:5],
        "safety_override": safety_override,
        "visual_evidence": visual_evidence,
        "area_ratio": area_ratio,
        "length_ratio": length_ratio,
        "width_ratio": width_ratio,
        "detection_quality": detection_quality,
        "image_features_used": True,
    }


def build_recommendation(inputs: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    severity = result.get("severity", "Low")
    element = str(inputs.get("element", "Other / unknown"))

    if severity == "Critical":
        return {
            "level": "CRITICAL",
            "headline": "Potentially significant condition — urgent professional assessment",
            "next_step": (
                "Do not rely on this image-based result to approve continued use or a repair. "
                "Arrange urgent assessment by a qualified structural professional. If there is an immediate "
                "danger of collapse or falling material, keep people away and follow local emergency procedures."
            ),
            "safe_actions": [
                "Document the condition without putting yourself in danger.",
                "Keep people away from any visibly unsafe area.",
                "Do not drill, cut, chip, load, or structurally repair the affected area yourself.",
            ],
            "remedy": (
                "A repair category cannot safely be prescribed from the image alone. Depending on the confirmed cause, "
                "professional repair could involve concrete/masonry repair, corrosion treatment, movement/settlement "
                "remediation, or another engineered solution."
            ),
            "why": (
                "The screening detected one or more visual or contextual indicators that can be associated with potentially significant damage."
            ),
            "inspection_required": True,
            "safety_override": True,
        }

    if severity == "High":
        return {
            "level": "HIGH",
            "headline": "High-priority condition — professional inspection recommended promptly",
            "next_step": (
                "Arrange a qualified inspection before carrying out structural repairs. "
                "Document the crack and monitor visible changes in the meantime."
            ),
            "safe_actions": [
                "Photograph and record the location/date.",
                "Avoid unnecessary loading or disturbance of the affected area until it is assessed.",
                "Do not cover the crack with a cosmetic repair before documentation/inspection.",
            ],
            "remedy": (
                "Possible remedy depends on the confirmed cause. It may include concrete or masonry repair, "
                "moisture-source correction, corrosion-related repair, or movement/settlement remediation. "
                "Do not select a structural repair solely from this screening."
            ),
            "why": (
                "The combination of visual extent and contextual indicators suggests that a simple surface fix may be inappropriate."
            ),
            "inspection_required": True,
            "safety_override": False,
        }

    if severity == "Moderate":
        return {
            "level": "MODERATE",
            "headline": "Moderate condition — inspect, document and monitor",
            "next_step": (
                "Arrange a professional inspection if the crack is in a structural element, is growing, "
                "or its cause is uncertain. Continue consistent photo monitoring."
            ),
            "safe_actions": [
                "Record the date, location and visible dimensions.",
                "Retake photos from the same angle, distance, lighting and scale.",
                "Watch for widening, lengthening, reopening, moisture, rust or new connected cracks.",
            ],
            "remedy": (
                "If a professional confirms that it is a non-structural surface crack, an appropriate "
                "surface crack filler/sealant or finish repair may be considered according to the product "
                "instructions. If the cause is moisture, movement or deterioration, that cause should be addressed "
                "rather than simply covering the crack."
            ),
            "why": (
                "Moderate conditions may be maintenance-related, but the available visual evidence is not enough to confirm the cause."
            ),
            "inspection_required": element in {"Beam", "Column", "Foundation"},
            "safety_override": False,
        }

    if element in {"Beam", "Column", "Foundation"}:
        inspection_text = (
            "Because the selected element is structural, professional inspection is still recommended before any structural repair."
        )
    else:
        inspection_text = (
            "If the crack remains small, stable and clearly surface-level, simple non-structural maintenance may be considered after documenting it."
        )

    return {
        "level": "LOW",
        "headline": "Low preliminary severity — monitor and consider simple maintenance only if non-structural",
        "next_step": inspection_text,
        "safe_actions": [
            "Photograph and document the crack before changing it.",
            "Monitor for widening, lengthening, reopening, moisture or new cracks.",
            "Keep future photos consistent in angle, lighting, distance and scale.",
        ],
        "remedy": (
            "For a confirmed non-structural surface crack, a suitable crack filler/sealant or surface finish repair may be considered "
            "according to the product instructions. Do not use a cosmetic repair to conceal a crack whose cause or structural significance is uncertain."
        ),
        "why": (
            "No strong high-risk indicators were identified by the explainable screening rules."
        ),
        "inspection_required": element in {"Beam", "Column", "Foundation"},
        "safety_override": False,
    }
