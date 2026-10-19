import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
PROHIBITED_LAYER_IMPORTS = {
    "fastapi",
    "sqlalchemy",
    "punq",
    "jwt",
    "pwdlib",
    "dotenv",
}


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_context_models_preserve_database_tables_and_indexes(self) -> None:
        from src.bootstrap.model_registry import Base

        self.assertEqual(
            set(Base.metadata.tables),
            {"audit_events", "companies", "invitations", "memberships", "users"},
        )
        self.assertEqual(
            {
                index.name
                for table in Base.metadata.tables.values()
                for index in table.indexes
            },
            {
                "uq_invitations_company_email_lower",
                "uq_memberships_active_user_company",
                "uq_users_email_lower",
            },
        )

    def test_domain_and_application_layers_do_not_import_infrastructure_libraries(
        self,
    ) -> None:
        violations: list[str] = []
        for layer in ("domain", "application"):
            for source_path in (SRC_ROOT / layer).rglob("*.py"):
                tree = ast.parse(source_path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        modules = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        modules = [node.module]
                    else:
                        continue
                    for module in modules:
                        top_module = module.split(".", maxsplit=1)[0]
                        if (
                            top_module in PROHIBITED_LAYER_IMPORTS
                            or module.startswith("src.infrastructure")
                            or module.startswith("src.presentation")
                            or module.startswith("src.bootstrap")
                        ):
                            violations.append(
                                f"{source_path.relative_to(PROJECT_ROOT)}:{node.lineno} "
                                f"imports {module}"
                            )

        self.assertEqual(violations, [])

    def test_presentation_does_not_depend_on_application_bootstrap(self) -> None:
        violations: list[str] = []
        for source_path in (SRC_ROOT / "presentation").rglob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if (
                        node.module.startswith("src.bootstrap")
                        or node.module.startswith("src.main")
                    ):
                        violations.append(
                            f"{source_path.relative_to(PROJECT_ROOT)}:{node.lineno} "
                            f"imports {node.module}"
                        )

        self.assertEqual(violations, [])

    def test_presentation_does_not_depend_on_concrete_infrastructure(self) -> None:
        prohibited_presentation_imports = PROHIBITED_LAYER_IMPORTS - {"fastapi"}
        violations: list[str] = []
        for source_path in (SRC_ROOT / "presentation").rglob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                else:
                    continue
                for module in modules:
                    top_module = module.split(".", maxsplit=1)[0]
                    if (
                        ".infrastructure" in module
                        or module.startswith("src.infrastructure")
                        or top_module in prohibited_presentation_imports
                    ):
                        violations.append(
                            f"{source_path.relative_to(PROJECT_ROOT)}:{node.lineno} "
                            f"imports {module}"
                        )

        self.assertEqual(violations, [])

    def test_authentication_behavior_is_not_defined_at_module_level(self) -> None:
        source_paths = [
            *list((SRC_ROOT / "domain" / "authentication").rglob("*.py")),
            *list((SRC_ROOT / "application" / "authentication").rglob("*.py")),
            *list((SRC_ROOT / "infrastructure" / "authentication").rglob("*.py")),
            *list((SRC_ROOT / "presentation" / "api" / "authentication").rglob("*.py")),
            SRC_ROOT / "bootstrap" / "authentication.py",
        ]
        violations = []
        for source_path in source_paths:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    violations.append(
                        f"{source_path.relative_to(PROJECT_ROOT)}:{node.lineno} "
                        f"defines {node.name} outside a class"
                    )

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
