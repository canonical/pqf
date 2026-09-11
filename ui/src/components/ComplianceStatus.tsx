interface Props {
  meetsTarget: boolean
  size?: 'small' | 'default'
}

/**
 * Compact status chip showing whether a product or dimension is at or above its target medal.
 * Renders directly from the payload's `meets_target` field — never recomputes medal comparisons.
 * Replaces the removed drift/remediation `DriftChip` now that the engine reports compliance
 * progress instead of remediation deadlines.
 */
export default function ComplianceStatus({ meetsTarget, size = 'default' }: Props) {
  return (
    <span
      style={{
        backgroundColor: meetsTarget ? '#0e8420' : '#C7162B',
        color: '#fff',
        borderRadius: '0.25rem',
        padding: size === 'small' ? '0.1rem 0.4rem' : '0.2rem 0.6rem',
        fontSize: size === 'small' ? '0.75rem' : '0.875rem',
        fontWeight: 600,
        display: 'inline-block',
        whiteSpace: 'nowrap',
      }}
    >
      {meetsTarget ? 'Meets target' : 'Below target'}
    </span>
  )
}
