"""Load a complete input set and check that its files agree with each other."""

from pathlib import Path

from pydantic import BaseModel

from bom_to_pcf.io.bom_reader import read_bom, read_routing
from bom_to_pcf.io.supplier_reader import read_supplier_pcfs, read_suppliers, read_transport
from bom_to_pcf.models import (
    BomLine,
    Issue,
    ProductConfig,
    RoutingStep,
    Severity,
    Supplier,
    SupplierPcf,
    TransportLeg,
)

BOM_FILE = "bom_export_sap_mock.csv"
ROUTING_FILE = "routing_energy_mock.csv"
SUPPLIER_PCF_FILE = "supplier_pcf.json"
SUPPLIERS_FILE = "suppliers.csv"
TRANSPORT_FILE = "transport_legs.csv"


class InputBundle(BaseModel):
    """Everything read from one input set, with all validation findings."""

    bom: list[BomLine] = []
    routing: list[RoutingStep] = []
    supplier_pcfs: list[SupplierPcf] = []
    suppliers: list[Supplier] = []
    transport: list[TransportLeg] = []
    issues: list[Issue] = []

    @property
    def has_errors(self) -> bool:
        return any(issue.severity is Severity.ERROR for issue in self.issues)


def load_inputs(config: ProductConfig, input_dir: Path | str | None = None) -> InputBundle:
    """Read all input files from a folder (default: the config's input_dir) and validate them."""
    folder = Path(input_dir if input_dir is not None else config.input_dir)
    bundle = InputBundle()

    def read(source: str, filename: str, reader) -> list:
        path = folder / filename
        if not path.is_file():
            bundle.issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="file_missing",
                    source=source,
                    message=f"{filename} was not found in {folder}.",
                )
            )
            return []
        records, issues = reader(path)
        bundle.issues.extend(issues)
        return records

    bundle.bom = read("bom", BOM_FILE, lambda path: read_bom(path, config))
    bundle.routing = read("routing", ROUTING_FILE, lambda path: read_routing(path, config))
    bundle.supplier_pcfs = read(
        "supplier_pcf", SUPPLIER_PCF_FILE, lambda path: read_supplier_pcfs(path, config)
    )
    bundle.suppliers = read("suppliers", SUPPLIERS_FILE, read_suppliers)
    bundle.transport = read("transport", TRANSPORT_FILE, read_transport)
    bundle.issues.extend(cross_check(bundle))
    return bundle


def cross_check(bundle: InputBundle) -> list[Issue]:
    """Find references between files that do not resolve."""
    issues: list[Issue] = []
    known_suppliers = {supplier.supplier_id for supplier in bundle.suppliers}
    bom_materials = {line.material_number for line in bundle.bom}
    transported = {leg.material_number for leg in bundle.transport}

    def warn(source: str, code: str, message: str, material: str) -> None:
        issues.append(
            Issue(
                severity=Severity.WARNING,
                code=code,
                source=source,
                message=message,
                material=material,
            )
        )

    for line in bundle.bom:
        if line.supplier_id and line.supplier_id not in known_suppliers:
            warn("bom", "unknown_supplier",
                 f"Supplier {line.supplier_id} is not in the supplier master data.",
                 line.material_number)  # fmt: skip
        if line.material_number not in transported:
            warn("transport", "no_transport_leg",
                 "No inbound transport leg for this material.", line.material_number)  # fmt: skip
    for pcf in bundle.supplier_pcfs:
        if pcf.material_number not in bom_materials:
            warn("supplier_pcf", "unknown_material",
                 f"{pcf.supplier_id} submitted data for a material not in the BOM.",
                 pcf.material_number)  # fmt: skip
    for leg in bundle.transport:
        if leg.material_number not in bom_materials:
            warn("transport", "unknown_material",
                 f"Transport leg {leg.leg_id} refers to a material not in the BOM.",
                 leg.material_number)  # fmt: skip
    return issues
