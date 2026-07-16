import styles from './SearchBar.module.css'

interface Props {
  value: string
  onChange: (value: string) => void
  onSearch: () => void
  placeholder?: string
}

const SearchBar = ({ value, onChange, onSearch, placeholder = 'Buscar nodos...' }: Props) => {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') onSearch()
  }

  return (
    <div className={styles.wrapper}>
      <input
        className={styles.input}
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
      />
      <button className={styles.button} onClick={onSearch}>
        Buscar
      </button>
    </div>
  )
}

export default SearchBar
