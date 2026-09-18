/**
 * Yuklanish paytida sahifa shakli ko'rinib turishi uchun.
 *
 * Nega kerak: ilgari sahifa bo'sh turib, keyin birdan to'lardi — bu
 * sekinroq his qilinadi, garchi vaqt bir xil bo'lsa ham. Skeleton
 * kutish davomida nima kelishini ko'rsatadi va sakrashni yo'qotadi.
 */

/** Bitta kulrang chiziq. Kengligi foizda beriladi. */
export function Line({ width = '100%', height = 12 }: { width?: string; height?: number }) {
  return <span className="sk-line" style={{ width, height }} />
}

/** Ko'rsatkich kartalari o'rnida turadigan shakl. */
export function CardsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="metric-grid" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <article key={index} className="metric-card sk-card">
          <div className="metric-top"><Line width="46%" height={11} /><span className="sk-round" /></div>
          <Line width="72%" height={26} />
          <Line width="54%" height={10} />
        </article>
      ))}
    </div>
  )
}

/** Jadval o'rnida turadigan shakl. */
export function TableSkeleton({ rows = 6, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <div className="table-wrap" aria-hidden="true">
      <table className="sk-table">
        <tbody>
          {Array.from({ length: rows }, (_, row) => (
            <tr key={row}>
              {Array.from({ length: columns }, (_, column) => (
                <td key={column}>
                  <Line width={column === 0 ? '70%' : column === columns - 1 ? '40%' : '55%'} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Grafik o'rnida turadigan shakl — ustunlar balandligi turlicha. */
export function ChartSkeleton({ bars = 7 }: { bars?: number }) {
  const heights = [52, 78, 41, 88, 63, 95, 70]
  return (
    <div className="sk-chart" aria-hidden="true">
      {Array.from({ length: bars }, (_, index) => (
        <span key={index} className="sk-bar" style={{ height: `${heights[index % heights.length]}%` }} />
      ))}
    </div>
  )
}

/** Panel ichidagi umumiy shakl: sarlavha va bir nechta qator. */
export function PanelSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="sk-panel" aria-hidden="true">
      <Line width="34%" height={14} />
      {Array.from({ length: rows }, (_, index) => (
        <Line key={index} width={`${88 - index * 9}%`} />
      ))}
    </div>
  )
}
