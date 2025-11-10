# Contributing to BayanLab Backbone

**Note:** BayanLab Backbone is currently a proprietary project. External contributions are not accepted at this time.

This document is for internal BayanLab team members and authorized partners only.

---

## For Internal Contributors

### Getting Started

1. **Clone the repository**
   ```bash
   git clone https://github.com/bayanlab/backbone.git
   cd bayanlab
   ```

2. **Set up development environment**
   ```bash
   uv sync
   cd infra/docker && docker-compose up -d db && cd ../..
   ```

3. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

---

## Development Workflow

### 1. Make Changes

- Follow existing code style (see Code Standards below)
- Write tests for new features
- Update documentation if needed

### 2. Test Locally

```bash
# Run tests
uv run pytest backend/tests/ -v

# Run pipeline
uv run python run_pipeline.py --pipeline all

# Start API and test manually
uv run uvicorn backend.services.api_service.main:app --reload
curl http://localhost:8000/v1/metrics
```

### 3. Commit Changes

Use conventional commits format:

```bash
git commit -m "feat: add new data source for Texas region"
git commit -m "fix: handle empty ICS responses gracefully"
git commit -m "docs: update setup guide with troubleshooting"
```

**Commit prefixes:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `refactor:` - Code refactoring (no functional changes)
- `test:` - Add or update tests
- `chore:` - Maintenance tasks (dependencies, config)

### 4. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

---

## Code Standards

### Python Style

- Follow PEP 8 (enforced by `ruff`)
- Use type hints for all functions
- Maximum line length: 100 characters
- Use `black` for formatting

```bash
# Format code
uv run black backend/

# Lint
uv run ruff backend/

# Type check
uv run mypy backend/
```

### Database Queries

- Always wrap raw SQL with `text()` for SQLAlchemy 2.0
- Use parameterized queries (never string interpolation)
- Add indexes for frequently queried columns

```python
# Good
session.execute(text("SELECT * FROM events WHERE region = :region"), {"region": "CO"})

# Bad
session.execute(f"SELECT * FROM events WHERE region = '{region}'")
```

### Logging

Use structured logging (JSON format):

```python
from backend.services.common.logger import get_logger

logger = get_logger("service_name")

logger.info("Event ingested", extra={
    "event_id": event_id,
    "source": "ics"
})
```

---

## Testing Requirements

### Unit Tests

- Test individual functions in isolation
- Mock external dependencies (API calls, database)
- Place in `backend/tests/unit/`

### Integration Tests

- Test services with real database
- Mock external APIs only
- Place in `backend/tests/integration/`

### Coverage

- Maintain > 70% test coverage
- New features must include tests

---

## Documentation

### Update These Files When:

- **README.md** - Major features or architecture changes
- **CHANGELOG.md** - Every release (use conventional commits)
- **docs/setup.md** - Installation or configuration changes
- **docs/roadmap.md** - New phases or strategic shifts
- **docs/decisions.md** - Major architectural decisions
- **docs/troubleshooting.md** - New common issues

---

## Pull Request Process

### Before Submitting

- [ ] Tests pass (`uv run pytest backend/tests/ -v`)
- [ ] Pipeline runs successfully
- [ ] Code formatted (`black`, `ruff`)
- [ ] Documentation updated if needed
- [ ] Commit messages follow conventional format

### PR Template

```markdown
## Summary
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How did you test this?

## Checklist
- [ ] Tests pass
- [ ] Pipeline runs
- [ ] Documentation updated
```

### Review Process

- All PRs require 1 approval from team lead
- Address review comments promptly
- Squash commits before merging (keep history clean)

---

## Release Process

### Versioning

We use [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes (1.0.0 → 2.0.0)
- **MINOR**: New features, backwards compatible (1.0.0 → 1.1.0)
- **PATCH**: Bug fixes (1.0.0 → 1.0.1)

### Creating a Release

1. Update `CHANGELOG.md` with release notes
2. Create and push a git tag:
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```
3. Deploy to production (see deployment docs)

---

## Questions?

**Internal Team:** Slack #bayanlab-dev
**Email:** info@bayanlab.com

---

**Last Updated:** November 10, 2025
