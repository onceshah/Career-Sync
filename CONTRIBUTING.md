# Contributing to CareerSync

Thank you for contributing to **CareerSync**! This document outlines developer guidelines, coding practices, testing expectations, and pull request workflows.

---

## 1. Lightweight Engineering Workflow

CareerSync follows a lightweight 5-step engineering process:

```text
  1. Understand  ──►  2. Implement  ──►  3. Test  ──►  4. Review  ──►  5. Document
```

1. **Understand**: Inspect existing code, domain enums, and architecture specifications (`docs/ARCHITECTURE.md`) before modifying modules.
2. **Implement**: Keep business logic in `app/domain/`, AI prompts in `app/ai/`, and I/O providers in `app/ingestion/` or `app/execution/`.
3. **Test**: Write Pytest unit tests for every new feature or bug fix.
4. **Review**: Ensure no unredacted PII is logged or passed to external APIs.
5. **Document**: Update the relevant developer guide in `docs/` if modifying configurations or schemas.

---

## 2. Code Style & Standards

* **Language Version**: Python 3.12+
* **Type Annotations**: Use static type annotations on all function signatures.
* **Docstrings**: Maintain standard Google-style docstrings for public classes and methods.
* **Format & Imports**: Use standard Python code layout with standard library imports first, third-party packages second, and internal `app.` modules third.

---

## 3. Branching & Pull Request (PR) Workflow

1. **Create Topic Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Commit Guidelines**:
   Keep commit messages concise and descriptive:
   ```text
   feat(domain): add support for referral stage in ATS state machine
   fix(ingestion): prevent fail-closed crash on missing phone recognizer
   ```

3. **Run Verification Before Submission**:
   ```bash
   # Run full test suite
   pytest

   # Verify no syntax errors
   python -m py_compile main.py
   ```

4. **Submit Pull Request**:
   * Include a description of what was changed and why.
   * Provide the `pytest` execution summary.
   * Cross-reference relevant deliverable IDs (e.g. D5, D6).
