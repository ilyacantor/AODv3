"""
Fabric API Routes - Industry-Weighted Vendor Selection

These endpoints proxy Farm's refined fabric plane APIs, which provide
industry-weighted vendor selection for realistic enterprise simulation.

Farm's Fabric API:
- GET /api/fabric/industries: Lists 9 industry verticals
- GET /api/fabric/weights/{industry}: Vendor probabilities per industry
- POST /api/fabric/generate: Generate deterministic fabric config
- GET /api/fabric/weights-matrix: Complete vendor weight matrix

Industry Verticals:
- finance: Banks/insurance (MuleSoft 55%, Apigee 50%, Confluent 45%)
- healthcare: Hospitals/pharma with HIPAA focus
- manufacturing: Industrial with edge computing
- logistics: Supply chain and fleet management
- tech_saas: Cloud-native startups (Workato, AWS Gateway)
- retail: E-commerce omnichannel
- media: Streaming/gaming high throughput
- government: FedRAMP/FISMA sovereign cloud
- energy: Utilities with NERC-CIP focus

Determinism: Same seed + industry always produces identical fabric config.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..schemas import (
    IndustryListResponse,
    IndustryVertical,
    IndustryWeightsResponse,
    PlaneWeights,
    VendorWeight,
    WeightsMatrixResponse,
    WeightsMatrixEntry,
    FabricGenerateRequest,
    FabricGenerateResponse,
    GeneratedVendorSelection,
)
from ..deps import get_farm_client

router = APIRouter(prefix="/fabric")


def _farm_error_response(error_type: str, error: str, status_code: int = 503) -> JSONResponse:
    """Return standardized JSON error for Farm failures."""
    return JSONResponse(
        status_code=status_code,
        content={"ok": False, "error": error_type, "detail": error}
    )


@router.get("/industries", response_model=IndustryListResponse)
async def list_industries():
    """
    List all available industry verticals.

    Returns 9 industry verticals with their compliance focus and typical scale:
    - finance: Banks/insurance - SOX, PCI-DSS
    - healthcare: Hospitals/pharma - HIPAA
    - manufacturing: Industrial - edge computing focus
    - logistics: Supply chain - fleet management
    - tech_saas: Cloud-native - Workato, AWS Gateway
    - retail: E-commerce - omnichannel focus
    - media: Streaming/gaming - high throughput
    - government: FedRAMP/FISMA - sovereign cloud
    - energy: Utilities - NERC-CIP

    These industries determine vendor selection probabilities when generating
    fabric configurations.
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.list_industries()

    if not result.success:
        status = 404 if result.error_type == "INDUSTRY_NOT_FOUND" else 503
        return _farm_error_response(result.error_type, result.error, status)

    data = result.data
    if isinstance(data, list):
        industries = [
            IndustryVertical(
                id=ind.get("id", ind.get("industry", "")),
                name=ind.get("name", ind.get("industry_name", "")),
                compliance_focus=ind.get("compliance_focus", []),
                typical_scale=ind.get("typical_scale", "medium"),
                description=ind.get("description")
            )
            for ind in data
        ]
    elif isinstance(data, dict) and "industries" in data:
        industries = [
            IndustryVertical(
                id=ind.get("id", ind.get("industry", "")),
                name=ind.get("name", ind.get("industry_name", "")),
                compliance_focus=ind.get("compliance_focus", []),
                typical_scale=ind.get("typical_scale", "medium"),
                description=ind.get("description")
            )
            for ind in data["industries"]
        ]
    else:
        industries = []

    return IndustryListResponse(industries=industries, count=len(industries))


@router.get("/weights/{industry}", response_model=IndustryWeightsResponse)
async def get_industry_weights(industry: str):
    """
    Get vendor selection weights for a specific industry.

    Returns probability weights for each vendor within each fabric plane type.
    These weights reflect industry-specific vendor preferences:

    Example (Finance):
    - iPaaS: MuleSoft (55%), Workato (20%), Boomi (15%)
    - API Gateway: Apigee (50%), Kong (25%), AWS Gateway (15%)
    - Event Bus: Confluent/Kafka (45%), EventBridge (30%)
    - Warehouse: Snowflake (40%), BigQuery (30%)

    Args:
        industry: Industry ID (e.g., 'finance', 'healthcare', 'tech_saas')

    Returns:
        Vendor weights organized by fabric plane type.
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.get_industry_weights(industry)

    if not result.success:
        status = 404 if result.error_type == "INDUSTRY_NOT_FOUND" else 503
        return _farm_error_response(result.error_type, result.error, status)

    data = result.data

    # Parse the response into structured format
    planes = []
    if isinstance(data, dict):
        # Handle nested planes structure
        planes_data = data.get("planes", [])
        if isinstance(planes_data, list):
            for plane in planes_data:
                vendors = [
                    VendorWeight(
                        vendor=v.get("vendor", ""),
                        weight=v.get("weight", 0.0),
                        display_name=v.get("display_name")
                    )
                    for v in plane.get("vendors", [])
                ]
                planes.append(PlaneWeights(
                    plane_type=plane.get("plane_type", ""),
                    vendors=vendors
                ))
        # Handle flat vendor weights structure
        elif "weights" in data:
            for plane_type, vendors_dict in data.get("weights", {}).items():
                vendors = [
                    VendorWeight(vendor=vendor, weight=weight)
                    for vendor, weight in vendors_dict.items()
                ]
                planes.append(PlaneWeights(plane_type=plane_type, vendors=vendors))

    return IndustryWeightsResponse(
        industry=data.get("industry", industry),
        industry_name=data.get("industry_name", industry.replace("_", " ").title()),
        planes=planes,
        compliance_focus=data.get("compliance_focus", [])
    )


@router.get("/weights-matrix", response_model=WeightsMatrixResponse)
async def get_weights_matrix():
    """
    Get the complete vendor weights matrix across all industries.

    Returns a matrix showing vendor selection weights for every combination
    of industry and fabric plane type. Useful for:
    - Visualizing industry-specific vendor preferences
    - Comparing vendor adoption across industries
    - Understanding the fabric plane ecosystem

    The matrix is organized as a flat list of entries for easy processing,
    along with helper arrays listing all industries, plane types, and vendors.
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.get_weights_matrix()

    if not result.success:
        return _farm_error_response(result.error_type, result.error)

    data = result.data

    # Parse matrix into structured format
    matrix = []
    industries_set = set()
    plane_types_set = set()
    vendors_set = set()

    if isinstance(data, dict):
        # Handle pre-structured matrix
        if "matrix" in data:
            for entry in data["matrix"]:
                matrix.append(WeightsMatrixEntry(
                    industry=entry.get("industry", ""),
                    plane_type=entry.get("plane_type", ""),
                    vendor=entry.get("vendor", ""),
                    weight=entry.get("weight", 0.0)
                ))
                industries_set.add(entry.get("industry", ""))
                plane_types_set.add(entry.get("plane_type", ""))
                vendors_set.add(entry.get("vendor", ""))
        # Handle nested structure: {industry: {plane_type: {vendor: weight}}}
        else:
            for industry, planes in data.items():
                if isinstance(planes, dict):
                    industries_set.add(industry)
                    for plane_type, vendors in planes.items():
                        if isinstance(vendors, dict):
                            plane_types_set.add(plane_type)
                            for vendor, weight in vendors.items():
                                vendors_set.add(vendor)
                                matrix.append(WeightsMatrixEntry(
                                    industry=industry,
                                    plane_type=plane_type,
                                    vendor=vendor,
                                    weight=weight
                                ))

    return WeightsMatrixResponse(
        matrix=matrix,
        industries=sorted(industries_set),
        plane_types=sorted(plane_types_set),
        vendors=sorted(vendors_set)
    )


@router.post("/generate", response_model=FabricGenerateResponse)
async def generate_fabric(request: FabricGenerateRequest):
    """
    Generate a fabric configuration using industry-weighted vendor selection.

    Uses the industry's vendor weights to probabilistically select vendors
    for each fabric plane type. The selection is deterministic: same seed
    + industry always produces identical results.

    Args:
        request.industry: Industry ID (e.g., 'finance', 'healthcare')
        request.seed: Optional seed for deterministic generation
        request.scale: Enterprise scale ('small', 'medium', 'large')

    Returns:
        Generated fabric configuration with selected vendors per plane.
        Includes the seed used (auto-generated if not provided) for reproducibility.

    Determinism:
        This endpoint preserves determinism for reproducible testing.
        Same seed + industry = identical fabric configuration every time.
    """
    farm_client = get_farm_client()
    if not farm_client:
        return _farm_error_response("NO_FARM_URL", "No Farm URL configured")

    result = await farm_client.generate_fabric(
        industry=request.industry,
        seed=request.seed,
        scale=request.scale
    )

    if not result.success:
        status = 404 if result.error_type == "INDUSTRY_NOT_FOUND" else 503
        return _farm_error_response(result.error_type, result.error, status)

    data = result.data

    # Parse fabric config into structured format
    fabric_config = []
    if isinstance(data, dict):
        for item in data.get("fabric_config", []):
            fabric_config.append(GeneratedVendorSelection(
                plane_type=item.get("plane_type", ""),
                vendor=item.get("vendor", ""),
                display_name=item.get("display_name", item.get("vendor", "").replace("_", " ").title()),
                confidence=item.get("confidence", item.get("weight", 1.0))
            ))

    return FabricGenerateResponse(
        industry=data.get("industry", request.industry),
        seed=data.get("seed", request.seed or 0),
        scale=data.get("scale", request.scale),
        fabric_config=fabric_config,
        deterministic=data.get("deterministic", True)
    )
