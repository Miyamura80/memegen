import pytest
import json
from src.services.meme.templates.loader import TemplateLoader

@pytest.fixture
def mock_templates_file(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    p = d / "templates.json"

    data = {
        "templates": [
            {
                "template_id": "t1",
                "name": "Test 1",
                "format": "two-panel",
                "image_path": "path/to/img1.jpg",
                "text_areas": "desc",
                "aspect_ratio": "1:1",
                "tags": ["funny", "cat"],
                "tone_affinity": ["wholesome"],
                "example_captions": [["c1", "c2"]]
            },
            {
                "template_id": "t2",
                "name": "Test 2",
                "format": "single",
                "image_path": "path/to/img2.jpg",
                "text_areas": "desc",
                "aspect_ratio": "16:9",
                "tags": ["sad", "dog"],
                "tone_affinity": ["dry"],
                "example_captions": [["c3"]]
            }
        ]
    }
    p.write_text(json.dumps(data))
    return p

def test_loader_load(mock_templates_file):
    loader = TemplateLoader(templates_file=mock_templates_file)
    templates = loader.list_templates()
    assert len(templates) == 2
    assert templates[0].name == "Test 1"

def test_loader_get(mock_templates_file):
    loader = TemplateLoader(templates_file=mock_templates_file)
    t = loader.get_template("t1")
    assert t is not None
    assert t.template_id == "t1"

    t2 = loader.get_template("nonexistent")
    assert t2 is None

def test_loader_filter(mock_templates_file):
    loader = TemplateLoader(templates_file=mock_templates_file)

    # Filter by format
    res = loader.filter_templates(format="two-panel")
    assert len(res) == 1
    assert res[0].template_id == "t1"

    # Filter by include_tags (ANY)
    res = loader.filter_templates(include_tags=["cat"])
    assert len(res) == 1
    assert res[0].template_id == "t1"

    res = loader.filter_templates(include_tags=["cat", "dog"])
    assert len(res) == 2

    # Filter by exclude_tags
    res = loader.filter_templates(exclude_tags=["cat"])
    assert len(res) == 1
    assert res[0].template_id == "t2"

    # Combined
    res = loader.filter_templates(include_tags=["funny"], format="two-panel")
    assert len(res) == 1
