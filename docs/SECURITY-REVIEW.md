# Runtime dependency review — 25 October 2026

Initial official `main` amd64 digest was from 6 October and the scan found 179 HIGH and 12 CRITICAL patchable findings. It is rejected for gateway activation. The historical Docker Hub runtime test image is retained only as evidence, not the final deployment choice.

Official stable v0.22.5 is dated 23 October, resolves to source bf0203a794a07aac3ff764972ab9087baa4e4f4e, and its pinned amd64 manifest is in container/versions.json. Its initial unfiltered scan reported 20 HIGH and 1 CRITICAL. The tag is unsigned and the image lacks an OCI revision label; release tag and registry identity were checked, not a signature attestation.

The custom image upgrades libbrotli1 through Debian security updates, installs exact fixed Python versions, and replaces affected installed Node package copies with exact fixed versions after verifying npm SHA-512 distribution integrity. Pins are recorded in container/security-pins.json. Existing nested Node dependencies are preserved, no npm lifecycle scripts run, and upstream lockfiles remain reference evidence; this is a deliberate downstream patch layer and must be reviewed again when upgrading upstream.

Two scanner findings need applicability review:

- CVE-2026-53869: Hermes image metadata says 0.0.0 while the actual CLI reports v0.22.5 and upstream bf0203a7. The advisory applies before 0.16.0. No web service or Ingress is deployed. The metadata discrepancy is not silently rewritten.
- CVE-2025-47273: setuptools 70.3.0 is reported from pip's embedded vendor SBOM at /opt/hermes/tools/python-3.14.9+20261021-linux-x64/lib/python3.14/site-packages/pip/_vendor/bom.cdx.json. Kubernetes inspection found no importable setuptools and no vulnerable setuptools/package_index.py module. A cached setuptools 84.2.0 distribution exists. The affected PackageIndex.download implementation is absent from the runtime.

No findings have been globally suppressed. The patched image unfiltered scan is https://github.com/egyhaty/hermes-assistant/actions/runs/40232364091 ; result pending. Raw scan artifacts stay in private Actions storage. Runtime startup for this patched digest still requires registry pull access and Kubernetes acceptance.

Codex `sandbox linux -- /bin/true` failed under the restricted pod with `bwrap: No permissions to create a new namespace`. No privileges or sandbox settings were weakened. Execution is not enabled.

The first patched scan eliminated all Debian/Node findings and the CRITICAL finding. Five HIGH results remained: Hermes placeholder metadata and pip's embedded vendor inventory for msgpack/urllib3/setuptools. The final layer removes the unused managed-interpreter pip installer and its vendored dependencies (PM/uv remains the supported installer), and corrects Hermes distribution metadata to the verified v0.22.5 CLI/source release. Installed msgpack 1.2.1 and urllib3 2.8.0 were present in the patched scan; older entries came only from pip's bundled SBOM. No scanner exception is used.

## Final result

The selected clean image in docs/build-receipts/clean-image.json passed the unfiltered scan with zero patchable HIGH/CRITICAL findings: https://github.com/egyhaty/hermes-assistant/actions/runs/40233184947 . No ignore file or VEX suppression was applied. The complete removal of unused pip and its affected vendor tree resolves the residual SBOM findings; accurate v0.22.5 release metadata resolves the placeholder-version match. See security-result.json for scope and date.
