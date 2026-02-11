# Contributing to Video Downloader

Thank you for considering contributing to this project! Here are some guidelines to help you get started.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](../../issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python/Node version, etc.)

### Suggesting Features

1. Check [Issues](../../issues) for existing feature requests
2. Create a new issue with:
   - Clear use case
   - Proposed solution or API design
   - Any relevant examples or mockups

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following the code style guidelines below
4. Write or update tests as needed
5. Ensure all tests pass
6. Update documentation if needed
7. Commit with clear messages (`git commit -m 'Add amazing feature'`)
8. Push to your branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## Development Setup

See [QUICKSTART.md](QUICKSTART.md) for local development instructions.

## Code Style Guidelines

### Backend (Python)

- Follow PEP 8 style guide
- Use type hints for all function signatures
- Run formatters before committing:
  ```bash
  uv run ruff format .
  uv run ruff check .
  uv run mypy app
  ```
- Write docstrings for public functions and classes
- Keep functions small and focused
- Add tests for new features

### Frontend (TypeScript/React)

- Use TypeScript strict mode
- Follow React best practices (hooks, functional components)
- Run formatters before committing:
  ```bash
  pnpm lint
  pnpm typecheck
  pnpm format
  ```
- Use semantic HTML
- Ensure components are accessible (ARIA labels, keyboard navigation)
- Add prop types and component documentation

## API Contract Changes

When modifying the API contract:

1. Update backend Pydantic models in `backend/app/models/video.py`
2. Update frontend zod schemas in `frontend/lib/api-client.ts`
3. Update API documentation in README.md
4. Run tests on both backend and frontend
5. Include migration notes in your PR description

## Testing

### Backend Tests

```bash
cd backend
uv run pytest
uv run pytest --cov=app --cov-report=html  # with coverage
```

### Frontend Tests

```bash
cd frontend
pnpm typecheck  # Type checking is our main test for now
pnpm lint       # Linting catches many issues
```

## Documentation

- Update README.md for user-facing changes
- Update inline code comments for complex logic
- Add examples for new features
- Keep deployment guides (RAILWAY.md) up to date

## Code Review Process

1. Maintainers will review your PR within a few days
2. Address any requested changes
3. Once approved, a maintainer will merge your PR

## Community Guidelines

- Be respectful and inclusive
- Help others learn and grow
- Focus on constructive feedback
- Celebrate contributions of all sizes

## Questions?

Feel free to open a Discussion or Issue if you have questions about contributing.

---

**Thank you for contributing to making this project better!** 🎉
