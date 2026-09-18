import { Coffee, Leaf, UtensilsCrossed, Wheat } from 'lucide-react'

interface Props {
  name: string
  category: string
  image?: string | null
}

export default function DishArt({ name, category, image }: Props) {
  const isSalad = category.includes('Salat')
  const isDrink = category.includes('Ichimlik')
  const isBread = category.includes('Non')
  const Icon = isSalad ? Leaf : isDrink ? Coffee : isBread ? Wheat : UtensilsCrossed

  const className = [
    'dish-art',
    isSalad && 'art-green',
    isDrink && 'art-tea',
    isBread && 'art-bread',
  ].filter(Boolean).join(' ')

  return (
    <div className={className}>
      {image ? (
        <img src={image} alt={name} loading="lazy" />
      ) : (
        <>
          <span className="plate"><Icon size={34} strokeWidth={1.25} /></span>
          <small>HONIM KITCHEN</small>
        </>
      )}
    </div>
  )
}
