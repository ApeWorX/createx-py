import importlib.resources
import json
from functools import cache
from typing import TYPE_CHECKING

from ethpm_types import PackageManifest

if TYPE_CHECKING:
    from ape.types import AddressType

DEPLOYER: "AddressType" = "0xeD456e05CaAb11d66C4c797dD6c1D6f9A7F352b5"
DEPLOYED_ADDRESS: "AddressType" = "0xba5Ed099633D3B313e4D5F7bdc1305d3c28ba5Ed"


DEPLOYED_CHAIN_IDS: list[int] = json.loads(
    (importlib.resources.files("createx") / "deployments.json").read_text()
)


@cache
def get_manifest():
    return PackageManifest.model_validate_json(
        (importlib.resources.files("createx") / "manifest.json").read_text()
    )


__all__ = [
    "DEPLOYED_ADDRESS",
    "DEPLOYED_CHAIN_IDS",
    "DEPLOYER",
    "get_manifest",
]
