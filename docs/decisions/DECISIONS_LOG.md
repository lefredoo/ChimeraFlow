# Decision Log

Chronological history of architectural and technical decisions.

---

## Entry Format

```markdown
## [YYYY-MM-DD] Short decision title

**Context**: Why this choice arose (1-2 sentences)
**Decision**: What was done
**Alternatives rejected**: What was discarded and why
**Consequences**: Impact on codebase (debt, future constraints)
**AGENTS.md rule concerned**: (if applicable)
```

---

## [2026-11-13] Project initialization with governance structure

**Context**: Creation of a new project requiring clear documentation and governance structure for AI agents and developers.

**Decision**: Adopt best practices from reference projects (Akili and Ancestria) including AGENTS.md for development guidelines, DESIGN.md for design system, structured docs/ directory, and two-branch Git workflow (main/dev).

**Alternatives rejected**: 
- Starting without documentation structure — would lead to inconsistent development practices
- Multiple feature branches — adds complexity without benefit for this project
- Storing configuration in code — violates security best practices

**Consequences**: 
- Solid foundation for future development
- Clear standards from day one
- All team members (human and AI) follow same conventions
- Technical decisions are documented and traceable

**AGENTS.md rule concerned**: §14 (DECISIONS_LOG mandatory), §5 (Git workflow)

---

_Add new entries at the top of this file (reverse chronological order)._
