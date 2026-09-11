# Compact Framework Version Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the global navigation height by retaining only the framework dropdown and a consistent refresh timestamp.

**Architecture:** `GlobalNav` remains responsible for navigation layout but no longer derives or renders framework context copy. `VersionSelector` remains responsible for selected-version metadata and renders the existing generated timestamp for every lifecycle status.

**Tech Stack:** React 19, TypeScript, React Testing Library, Vitest, Vanilla Framework.

## Global Constraints

- Keep the selector's accessible `Framework version` label.
- Preserve version grouping and route-preserving navigation.
- Render `Refreshed <local timestamp>` for active, upcoming, and archived versions.
- Remove only CSS and imports made obsolete by deleting the context sentence.

---

### Task 1: Compact the framework selector area

**Files:**
- Modify: `ui/src/components/GlobalNav.test.tsx`
- Modify: `ui/src/components/VersionSelector.test.tsx`
- Modify: `ui/src/components/GlobalNav.tsx`
- Modify: `ui/src/components/VersionSelector.tsx`
- Modify: `ui/src/index.css`

**Interfaces:**
- Consumes: `useFrameworkVersion()` and the existing `FrameworkVersionSummary.generated_at` value.
- Produces: the existing `VersionSelector` component with an always-visible refresh timestamp.

- [ ] **Step 1: Write the failing tests**

Replace the context-label assertion in `GlobalNav.test.tsx` with:

```tsx
it('does not render a separate framework context label', () => {
  wrap(<GlobalNav />)
  expect(screen.queryByText('Current framework · PQF V0')).not.toBeInTheDocument()
})
```

Replace the active-version timestamp test in `VersionSelector.test.tsx` with:

```tsx
it('shows the refreshed timestamp when the selected version is active', async () => {
  renderSelector('/v0/products/matrix')
  await screen.findByRole('combobox', { name: /framework version/i })
  expect(screen.getByText(/Refreshed/)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ui && npm test -- src/components/GlobalNav.test.tsx src/components/VersionSelector.test.tsx
```

Expected: the context-label test finds the existing text, and the active timestamp test cannot find `Refreshed`.

- [ ] **Step 3: Implement the compact layout**

In `GlobalNav.tsx`, remove `describeFrameworkContext`, the unused `current` value, and the context `<span>`, leaving:

```tsx
<div className="p-navigation__nav-selector-wrapper">
  <VersionSelector />
</div>
```

In `VersionSelector.tsx`, render the metadata span without a status condition:

```tsx
<span
  className="version-selector__meta"
  style={{ fontSize: '0.75rem', color: '#f2f2f2', marginTop: '0.25rem' }}
>
  Refreshed {new Date(current.generated_at).toLocaleString()}
</span>
```

In `index.css`, remove the context-label commentary, flex wrapping, row gap, and `.p-text--small` rules. Keep the selector wrapper aligned to the right:

```css
.p-navigation__nav-selector-wrapper {
  margin-left: auto;
  display: flex;
  align-items: center;
  padding: 0.5rem 1rem;
  max-width: 100%;
}

@media (max-width: 620px) {
  .p-navigation__nav-selector-wrapper {
    justify-content: flex-end;
    padding-top: 0;
  }
}
```

- [ ] **Step 4: Run focused and complete UI verification**

Run:

```bash
make test-ui && make build
```

Expected: 18 test files pass and the Vite production build exits successfully.

- [ ] **Step 5: Commit and push**

```bash
git add ui/src/components/GlobalNav.test.tsx ui/src/components/VersionSelector.test.tsx \
  ui/src/components/GlobalNav.tsx ui/src/components/VersionSelector.tsx ui/src/index.css \
  docs/superpowers/plans/2026-09-11-compact-version-selector.md
git commit -m "fix: compact framework version selector" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
git push
```
