import type { Medal, Result } from '../types'

type BadgeValue = Medal | Result

const MEDAL_COLOURS: Record<BadgeValue, string> = {
  gold: '#C7962F',
  silver: '#8F8F8F',
  bronze: '#9E622A',
  unrated: '#666',
  below_minimum: '#666',
  insufficient_data: '#666',
  not_applicable: '#666',
}

const MEDAL_LABELS: Record<BadgeValue, string> = {
  gold: 'Gold',
  silver: 'Silver',
  bronze: 'Bronze',
  unrated: 'Unrated',
  below_minimum: 'Below minimum',
  insufficient_data: 'Insufficient data',
  not_applicable: 'N/A',
}

interface Props {
  medal: BadgeValue
  size?: 'small' | 'default'
}

export default function MedalBadge({ medal, size = 'default' }: Props) {
  const bg = MEDAL_COLOURS[medal]
  const fontSize = size === 'small' ? '0.75rem' : '0.875rem'
  return (
    <span
      style={{
        backgroundColor: bg,
        color: '#fff',
        borderRadius: '0.25rem',
        padding: size === 'small' ? '0.1rem 0.4rem' : '0.2rem 0.6rem',
        fontSize,
        fontWeight: 600,
        minWidth: size === 'small' ? '7rem' : '8.5rem',
        display: 'inline-flex',
        justifyContent: 'center',
        alignItems: 'center',
        whiteSpace: 'nowrap',
      }}
    >
      {MEDAL_LABELS[medal]}
    </span>
  )
}
