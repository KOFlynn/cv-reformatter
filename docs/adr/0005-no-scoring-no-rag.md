# No candidate scoring, ranking, filtering, matching or search; therefore no RAG

Anything that evaluates or filters candidates would make this a high-risk AI system under EU AI Act Annex III, point 4 ("analyse and filter job applications, and to evaluate candidates"). The system reformats one CV at a time and never compares candidates to anything. This is a scope boundary, not a missing feature.

It also explains why the project's gap list deliberately leaves vector databases and RAG uncovered: nothing in reformatting needs retrieval, and the obvious RAG feature (candidate search) would breach the boundary above. Better to leave a gap open than close it with a feature that changes the system's regulatory category.
