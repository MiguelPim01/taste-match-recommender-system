import { Link } from "react-router";

import { iconFor, orderedCategories, primaryCategory } from "../categories";
import { Icon } from "./Icon";

/** The restaurant's sign: the icon of its most characteristic category, in brand mustard. */
export function Emblem({ categories, large }: { categories: string[]; large?: boolean }) {
  const primary = primaryCategory(categories);
  return (
    <span className={large ? "emblem emblem-large" : "emblem"} title={primary.name}>
      <Icon name={primary.icon} size={large ? 42 : 24} />
    </span>
  );
}

/** Categories as links to the filtered catalogue; the emblem's category comes first and stands out. */
export function CategoryChips({ categories, limit }: { categories: string[]; limit?: number }) {
  const ordered = orderedCategories(categories);
  const shown = limit ? ordered.slice(0, limit) : ordered;
  const hidden = ordered.length - shown.length;
  return (
    <ul className="chips" aria-label="Categorias">
      {shown.map((name, index) => {
        const icon = iconFor(name);
        return (
          <li key={name}>
            <Link className={index === 0 ? "chip chip-primary" : "chip"} to={`/explorar?categoria=${encodeURIComponent(name)}`}>
              {icon && <Icon name={icon} size={16} />}
              {name}
            </Link>
          </li>
        );
      })}
      {hidden > 0 && <li className="chip-more">e mais {hidden}</li>}
    </ul>
  );
}
