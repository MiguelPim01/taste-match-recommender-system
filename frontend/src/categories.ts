import type { IconName } from "./icons";

// Yelp categories grouped under the icon that represents them.
const GROUPS: Record<Exclude<IconName, "view" | "comment" | "rating">, string[]> = {
  hoagie: ["Cheesesteaks", "Sandwiches", "Delis", "Hot Dogs"],
  pizza: ["Pizza"],
  pasta: ["Italian"],
  sushi: ["Japanese", "Sushi Bars", "Poke"],
  bowl: ["Asian Fusion", "Vietnamese", "Korean", "Noodles", "Thai", "Ramen", "Malaysian", "Hot Pot", "Soup", "Pan Asian", "Filipino"],
  dumpling: ["Chinese", "Dim Sum", "Cantonese", "Shanghainese", "Szechuan", "Taiwanese"],
  taco: ["Mexican", "Tex-Mex", "Tacos", "Latin American", "Cuban", "Caribbean", "Brazilian", "Argentine", "Peruvian", "Colombian"],
  fish: ["Seafood", "Seafood Markets", "Fish & Chips"],
  flame: ["Barbeque", "Steakhouses", "Smokehouse", "Meat Shops"],
  egg: ["Breakfast & Brunch", "Diners", "Waffles", "Pancakes"],
  coffee: ["Coffee & Tea", "Cafes", "Bubble Tea", "Tea Rooms", "Coffee Roasteries"],
  cupcake: ["Desserts", "Bakeries", "Ice Cream & Frozen Yogurt", "Donuts", "Chocolatiers & Shops", "Bagels", "Candy Stores",
    "Patisserie/Cake Shop", "Creperies", "Gelato"],
  leaf: ["Vegetarian", "Vegan", "Salad", "Gluten-Free", "Juice Bars & Smoothies", "Fruits & Veggies", "Acai Bowls"],
  olive: ["Mediterranean", "Middle Eastern", "Greek", "Lebanese", "Halal", "Falafel", "Turkish", "Israeli", "Kosher", "Persian/Iranian"],
  pot: ["Indian", "Pakistani", "Comfort Food", "Soul Food", "Southern", "Ethiopian", "Himalayan/Nepalese", "Cajun/Creole", "Buffets"],
  skewer: ["Tapas/Small Plates", "Tapas Bars", "Spanish", "Iberian", "Basque"],
  burger: ["Burgers", "Fast Food", "Chicken Wings", "Chicken Shop"],
  cloche: ["American (New)", "French", "Modern European", "Caterers"],
  beer: ["Pubs", "Beer", "Gastropubs", "Beer Bar", "Sports Bars", "Beer Gardens", "Breweries", "Irish Pub", "Irish", "German", "Belgian"],
  cocktail: ["Cocktail Bars", "Lounges", "Wine Bars", "Wine & Spirits", "Whiskey Bars", "Nightlife", "Bars", "Dance Clubs",
    "Karaoke", "Jazz & Blues", "Music Venues", "Speakeasies"],
  market: ["Specialty Food", "Food Court", "Public Markets", "Grocery", "Cheese Shops", "Shopping", "Food Stands",
    "Farmers Market", "Department Stores"],
  plate: ["American (Traditional)"],
};

const ICON_OF = new Map<string, IconName>(
  Object.entries(GROUPS).flatMap(([icon, names]) => names.map((name) => [name, icon as IconName] as const)),
);

// Broad labels that half the catalog carries; they only decide the emblem when nothing more specific exists.
export const GENERIC = new Set(["Nightlife", "Bars", "American (New)", "American (Traditional)", "Local Flavor",
  "Specialty Food", "Event Planning & Services", "Venues & Event Spaces", "Arts & Entertainment", "Caterers",
  "Food Delivery Services"]);
// Categories that name what the place is, whatever else it lists; the order is the tie-break.
// Cheesesteaks first: this is a Philadelphia app.
const DEFINING = ["Cheesesteaks", "Public Markets", "Food Court", "Ramen", "Sushi Bars", "Dim Sum", "Pizza", "Tacos",
  "Burgers", "Noodles", "Hot Pot"];
const HIDDEN = new Set(["Restaurants", "Food"]);

export function iconFor(category: string): IconName | undefined {
  return ICON_OF.get(category);
}

/** The restaurant's emblem: a defining category if there is one, else Yelp's own order, broad labels last. */
export function primaryCategory(categories: string[]): { name: string; icon: IconName } {
  const shown = visibleCategories(categories);
  const pick = DEFINING.find((name) => shown.includes(name))
    ?? shown.find((name) => ICON_OF.has(name) && !GENERIC.has(name))
    ?? shown.find((name) => ICON_OF.has(name));
  return pick ? { name: pick, icon: ICON_OF.get(pick)! } : { name: shown[0] ?? "", icon: "plate" };
}

/** Categories worth showing, with the emblem's category first. */
export function visibleCategories(categories: string[]): string[] {
  return categories.filter((name) => !HIDDEN.has(name));
}

/** One category per icon, the most common one, for a row of shortcuts that shows every kind of place. */
export function cuisineShortcuts<T extends { name: string; count: number }>(categories: T[]): (T & { icon: IconName })[] {
  const seen = new Set<IconName>();
  const shortcuts: (T & { icon: IconName })[] = [];
  for (const category of [...categories].sort((a, b) => b.count - a.count)) {
    const icon = ICON_OF.get(category.name);
    if (!icon || GENERIC.has(category.name) || seen.has(icon)) continue;
    seen.add(icon);
    shortcuts.push({ ...category, icon });
  }
  return shortcuts;
}

export function orderedCategories(categories: string[]): string[] {
  const primary = primaryCategory(categories).name;
  const rest = visibleCategories(categories).filter((name) => name !== primary);
  return primary ? [primary, ...rest] : rest;
}
