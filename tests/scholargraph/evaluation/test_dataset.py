from scholargraph.evaluation import load_evaluation_dataset


def test_checked_in_dataset_covers_required_question_categories() -> None:
    dataset = load_evaluation_dataset()

    assert len(dataset.papers) == 6
    assert len(dataset.questions) == 6
    assert {question.category.value for question in dataset.questions} == {
        "fact",
        "cross_document",
        "dataset",
        "method",
        "relation",
        "multi_hop",
    }
    assert all(paper.source_url.startswith("https://arxiv.org/abs/") for paper in dataset.papers)
    assert all(paper.pdf_url.startswith("https://arxiv.org/pdf/") for paper in dataset.papers)

