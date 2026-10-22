Build the starting world state from the identity cards, scene context, and starting situation.
Return only a JSON object matching the supplied WorldState schema. Omit clock; code sets day 1 morning.
Include the input location in places, using KB location slugs for all places.
Give exactly the input characters whereabouts, goals seeded from their card's post-game motivation and the starting situation, and commitments (what, where, and when they have promised to be).
Give a `people` entry for every minor character the situations involve: their whereabouts (a slug in places), what they want (at least one), and their commitments. A person's name must not be a main character's.
Create 1–3 open situations, each with a `kind` (trouble, occasion, promise, wish, or reunion), touching at least one main character or their goals, naming the `people` entries involved, what happens next if nobody acts, and when it is due. Due times must not precede day 1 morning. With two or more situations, give them more than one kind, and spread their due parts so they are not all the same.
