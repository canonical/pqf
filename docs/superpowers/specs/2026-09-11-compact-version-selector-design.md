# Compact framework version selector

## Goal

Reduce the global navigation height by making the framework selector the sole indicator of the
currently displayed framework version.

## Design

- Remove the separate framework context sentence from `GlobalNav`.
- Keep the framework version selector in the navigation's right-hand control area.
- Show `Refreshed <local timestamp>` beneath the selector for every framework version, regardless
  of whether it is upcoming, active, or archived.
- Remove CSS that exists only to lay out and wrap the deleted context sentence.
- Preserve the selector's accessible off-screen label and version-group labels.

## Testing

- Assert the global navigation does not render the redundant framework context sentence.
- Assert the selector renders the refresh timestamp for both active and upcoming versions.
- Retain the existing route-preservation and accessible-label coverage.
