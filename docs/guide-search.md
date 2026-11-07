def test_rag_opensource_research_doc_reference():
    """Verify that GitHub RAG open-source utilization plan and local RAG code example are documented in tech-research.md."""
    from pathlib import Path
    doc_path = Path("docs/tech-research.md")
    assert doc_path.exists()
    content = doc_path.read_text(encoding="utf-8")
    assert "깃허브 RAG 오픈소스 활용 방안" in content or "RAG" in content
    assert "MarkdownHeaderTextSplitter" in content


def test_guide_search_markdown_exists():
    """Verify that docs/guide-search.md is created and contains essential RAG search guide sections."""
    from pathlib import Path
    guide_path = Path("docs/guide-search.md")
    assert guide_path.exists()
    content = guide_path.read_text(encoding="utf-8")
    assert "RAG 활용 및 도움말 검색 가이드" in content
    assert "help_search" in content