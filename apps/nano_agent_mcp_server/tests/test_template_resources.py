"""Tests for template_resources module."""

import pytest
from nano_agent.modules.template_resources import (
    TEMPLATE_REGISTRY,
    load_template,
    list_all_templates,
    register_template_resources,
)


class TestLoadTemplate:
    def test_load_agents_readme(self):
        content = load_template("agents", "README.md")
        assert "Nano-Agent Templates" in content

    def test_load_nano_reviewer(self):
        content = load_template("agents", "nano-reviewer.md")
        assert "nano-reviewer" in content.lower() or "reviewer" in content.lower()

    def test_load_identity_template(self):
        content = load_template("agent-identities", "general-coder/AGENT.md")
        assert "general" in content.lower() or "coder" in content.lower()

    def test_load_guide(self):
        content = load_template("guides", "when-to-use-what.md")
        assert "when" in content.lower() or "use" in content.lower()

    def test_load_skill_template(self):
        content = load_template("skills", "nano-dispatch/SKILL.md")
        assert "nano-dispatch" in content.lower() or "dispatch" in content.lower()

    def test_load_missing_file(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_template("agents", "nonexistent.md")

    def test_load_invalid_category(self):
        with pytest.raises(ValueError, match="Invalid category"):
            load_template("invalid", "README.md")

    def test_path_traversal_blocked(self):
        with pytest.raises((FileNotFoundError, ValueError)):
            load_template("agents", "../../__main__.py")

    def test_all_registered_templates_loadable(self):
        for entry in TEMPLATE_REGISTRY:
            content = load_template(entry["category"], entry["name"])
            assert len(content) > 0, f"Template {entry['category']}/{entry['name']} is empty"

    def test_registry_matches_actual_files(self):
        from importlib.resources import files
        base = files("nano_agent") / "templates"
        for entry in TEMPLATE_REGISTRY:
            path_parts = entry["name"].split("/")
            resource = base / entry["category"]
            for part in path_parts:
                resource = resource / part
            content = resource.read_text()
            assert len(content) > 0, f"File {entry['category']}/{entry['name']} not found or empty"

    def test_top_level_readme_with_empty_category(self):
        """Test loading the top-level README.md with empty category string."""
        content = load_template("", "README.md")
        assert len(content) > 0
        assert "template" in content.lower()


class TestListAllTemplates:
    def test_returns_valid_structure(self):
        result = list_all_templates()
        assert "templates" in result
        assert isinstance(result["templates"], list)

    def test_each_entry_has_required_fields(self):
        result = list_all_templates()
        for entry in result["templates"]:
            assert all(k in entry for k in ("uri", "category", "name", "description")), \
                f"Entry missing required fields: {entry}"

    def test_uris_use_correct_scheme(self):
        result = list_all_templates()
        for entry in result["templates"]:
            assert entry["uri"].startswith("nano-agent://templates/"), \
                f"URI does not use correct scheme: {entry['uri']}"


class TestMCPResourceRegistration:
    def test_custom_uri_scheme_accepted_by_fastmcp(self):
        """Verify FastMCP accepts nano-agent:// custom URI scheme."""
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP(name="test")

        @mcp.resource("nano-agent://templates/test")
        def test_resource() -> str:
            return "test"
        # Should not raise

    def test_register_returns_count(self):
        """register_template_resources returns count of registered resources."""
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP(name="test")
        count = register_template_resources(mcp)
        assert count == len(TEMPLATE_REGISTRY) + 1  # +1 for the index resource
