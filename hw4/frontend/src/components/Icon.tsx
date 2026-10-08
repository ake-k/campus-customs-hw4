// Thin line icons (1.6px stroke, currentColor) for the slim header and controls.

export type IconName =
  | 'search' | 'user' | 'size' | 'chat' | 'bag' | 'chevron' | 'close' | 'arrow' | 'check' | 'plus' | 'minus' | 'spark' | 'menu'

const PATHS: Record<IconName, string> = {
  search: 'M10.5 3.5a7 7 0 1 1 0 14 7 7 0 0 1 0-14zM20.5 20.5l-5-5',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4.5 20.5c.8-3.6 3.8-5.5 7.5-5.5s6.7 1.9 7.5 5.5',
  size: 'M3.5 8.5h17v7h-17zM7.5 8.5v3M11.5 8.5v4M15.5 8.5v3',
  chat: 'M4.5 6.5a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-7l-4.5 3.5v-3.5a2 2 0 0 1-1.5-2zM8.5 10.5h7M8.5 13h4',
  bag: 'M5.5 8.5h13l-1 12h-11zM9 8.5V7a3 3 0 0 1 6 0v1.5',
  chevron: 'M7 10l5 5 5-5',
  close: 'M6 6l12 12M18 6L6 18',
  arrow: 'M4.5 12h15M14 6.5l5.5 5.5-5.5 5.5',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  spark: 'M12 3.5l1.8 5.2 5.2 1.8-5.2 1.8L12 17.5l-1.8-5.2-5.2-1.8 5.2-1.8zM18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z',
  menu: 'M4 7h16M4 12h16M4 17h16',
}

export default function Icon({ name, size = 20, className = '' }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg className={`icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  )
}
