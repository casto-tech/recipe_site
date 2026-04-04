"""
Management command: load_sample_recipes

Loads 8 sample recipes with varied tags for local development and demos.
Uses get_or_create to be idempotent — safe to run multiple times.

Usage:
    python manage.py load_sample_recipes
"""

from django.core.management.base import BaseCommand
from django.utils.text import slugify

SAMPLE_TAGS = [
    "Italian",
    "Mexican",
    "American",
    "Vegetarian",
    "Dessert",
    "Asian",
    "Quick",
    "Comfort Food",
]

SAMPLE_RECIPES = [
    {
        "title": "Classic Spaghetti Carbonara",
        "tags": ["Italian"],
        "image_url": "https://picsum.photos/seed/carbonara/400/300",
        "ingredients": (
            "400g spaghetti\n"
            "200g pancetta or guanciale\n"
            "4 large eggs\n"
            "100g Pecorino Romano, finely grated\n"
            "50g Parmesan, finely grated\n"
            "2 garlic cloves\n"
            "Black pepper\n"
            "Salt"
        ),
        "directions": (
            "Bring a large pot of salted water to a boil and cook spaghetti until al dente.\n"
            "Meanwhile, cook pancetta in a pan over medium heat until crispy. Add garlic and cook 1 minute.\n"
            "Whisk together eggs, Pecorino, and Parmesan in a bowl. Season with black pepper.\n"
            "Reserve 1 cup of pasta cooking water, then drain spaghetti.\n"
            "Remove pan from heat. Add spaghetti and toss with pancetta fat.\n"
            "Add egg mixture and splash of pasta water. Toss quickly to create a creamy sauce.\n"
            "Serve immediately with extra cheese and cracked black pepper."
        ),
    },
    {
        "title": "Street-Style Beef Tacos",
        "tags": ["Mexican"],
        "image_url": "https://picsum.photos/seed/tacos/400/300",
        "ingredients": (
            "500g ground beef\n"
            "8 small corn tortillas\n"
            "1 white onion, finely diced\n"
            "2 cloves garlic, minced\n"
            "1 tsp cumin\n"
            "1 tsp smoked paprika\n"
            "1/2 tsp chilli powder\n"
            "Fresh cilantro\n"
            "Lime wedges\n"
            "Salsa verde\n"
            "Salt and pepper"
        ),
        "directions": (
            "Heat oil in a skillet over high heat. Add ground beef and cook until browned.\n"
            "Add onion and garlic. Cook 3 minutes until softened.\n"
            "Season with cumin, paprika, chilli powder, salt, and pepper. Cook 2 more minutes.\n"
            "Warm tortillas in a dry pan or directly over a gas flame.\n"
            "Fill tortillas with beef mixture.\n"
            "Top with diced onion, fresh cilantro, and a squeeze of lime.\n"
            "Serve with salsa verde on the side."
        ),
    },
    {
        "title": "Classic American Cheeseburger",
        "tags": ["American"],
        "image_url": "https://picsum.photos/seed/burger/400/300",
        "ingredients": (
            "700g ground beef (80/20)\n"
            "4 burger buns, toasted\n"
            "4 slices American cheese\n"
            "1 large white onion\n"
            "Iceberg lettuce\n"
            "2 tomatoes, sliced\n"
            "Dill pickles\n"
            "Ketchup and mustard\n"
            "Salt and pepper"
        ),
        "directions": (
            "Divide beef into 4 portions and shape into patties. Season generously with salt and pepper.\n"
            "Heat a cast-iron skillet or grill to high heat.\n"
            "Cook patties 3-4 minutes per side for medium. Add cheese in the last minute.\n"
            "Toast buns cut-side down in the same pan.\n"
            "Assemble: bottom bun, ketchup, mustard, lettuce, tomato, patty with cheese, pickles, top bun.\n"
            "Serve immediately."
        ),
    },
    {
        "title": "Roasted Tomato Basil Soup",
        "tags": ["Vegetarian", "Comfort Food"],
        "image_url": "https://picsum.photos/seed/tomatosoup/400/300",
        "ingredients": (
            "1kg ripe tomatoes, halved\n"
            "1 large onion, quartered\n"
            "6 garlic cloves\n"
            "3 tbsp olive oil\n"
            "500ml vegetable stock\n"
            "Large handful fresh basil\n"
            "1 tsp sugar\n"
            "Salt and pepper\n"
            "Cream, to serve"
        ),
        "directions": (
            "Preheat oven to 200°C.\n"
            "Place tomatoes, onion, and garlic on a baking tray. Drizzle with olive oil, season well.\n"
            "Roast for 35-40 minutes until caramelised and slightly charred at edges.\n"
            "Transfer roasted vegetables to a large saucepan. Add vegetable stock.\n"
            "Simmer for 10 minutes, then blend until smooth.\n"
            "Add basil, sugar, and adjust seasoning.\n"
            "Serve hot with a swirl of cream and crusty bread."
        ),
    },
    {
        "title": "Decadent Chocolate Lava Cakes",
        "tags": ["Dessert", "American"],
        "image_url": "https://picsum.photos/seed/lavacake/400/300",
        "ingredients": (
            "200g dark chocolate (70%), chopped\n"
            "200g unsalted butter\n"
            "4 eggs plus 4 egg yolks\n"
            "200g icing sugar\n"
            "80g plain flour\n"
            "Pinch of salt\n"
            "Vanilla ice cream, to serve\n"
            "Cocoa powder, for dusting"
        ),
        "directions": (
            "Preheat oven to 220°C. Butter and dust 6 ramekins with cocoa powder.\n"
            "Melt chocolate and butter together in a heatproof bowl over simmering water. Let cool slightly.\n"
            "Whisk eggs, egg yolks, and icing sugar until pale and thick.\n"
            "Fold chocolate mixture into egg mixture.\n"
            "Sift in flour and salt; fold gently until just combined.\n"
            "Divide batter between ramekins. Chill 30 minutes (or up to 24 hours).\n"
            "Bake 10-12 minutes until edges are set but centre still jiggles.\n"
            "Run a knife around edges and turn out onto plates. Serve with ice cream."
        ),
    },
    {
        "title": "Chicken Tikka Masala",
        "tags": ["Asian", "Comfort Food"],
        "image_url": "https://picsum.photos/seed/tikka/400/300",
        "ingredients": (
            "800g chicken thighs, cubed\n"
            "400ml coconut milk or cream\n"
            "400g tin crushed tomatoes\n"
            "1 large onion, finely diced\n"
            "4 garlic cloves, minced\n"
            "2 tsp fresh ginger, grated\n"
            "2 tsp garam masala\n"
            "2 tsp cumin\n"
            "1 tsp turmeric\n"
            "1 tsp coriander\n"
            "1 tsp chilli powder\n"
            "Salt\n"
            "Fresh cilantro\n"
            "Basmati rice, to serve"
        ),
        "directions": (
            "Marinate chicken in half the spices plus yoghurt for at least 1 hour.\n"
            "Grill or pan-fry marinated chicken until charred. Set aside.\n"
            "Sauté onion in oil until golden. Add garlic and ginger, cook 2 minutes.\n"
            "Add remaining spices and cook 1 minute until fragrant.\n"
            "Add crushed tomatoes and simmer 10 minutes.\n"
            "Add coconut milk or cream. Simmer 10 more minutes.\n"
            "Add chicken pieces and simmer until cooked through.\n"
            "Serve over basmati rice, garnished with fresh cilantro."
        ),
    },
    {
        "title": "Quick Avocado Toast",
        "tags": ["Vegetarian", "Quick"],
        "image_url": "https://picsum.photos/seed/avotoast/400/300",
        "ingredients": (
            "2 slices sourdough bread\n"
            "2 ripe avocados\n"
            "1 lemon, juiced\n"
            "Red chilli flakes\n"
            "Flaky sea salt\n"
            "2 eggs (optional)\n"
            "Microgreens or sprouts (optional)"
        ),
        "directions": (
            "Toast sourdough slices until golden and crisp.\n"
            "Halve avocados, remove stones, and scoop flesh into a bowl.\n"
            "Add lemon juice and a pinch of salt. Mash to your preferred texture.\n"
            "If using eggs, poach or fry them to your liking.\n"
            "Spread avocado generously over toast.\n"
            "Top with red chilli flakes, flaky salt, and microgreens.\n"
            "Place egg on top if using. Serve immediately."
        ),
    },
    {
        "title": "Banana Walnut Bread",
        "tags": ["Dessert", "American", "Quick"],
        "image_url": "https://picsum.photos/seed/bananabread/400/300",
        "ingredients": (
            "3 very ripe bananas\n"
            "80g unsalted butter, melted\n"
            "150g caster sugar\n"
            "1 egg, beaten\n"
            "1 tsp vanilla extract\n"
            "1 tsp baking soda\n"
            "Pinch of salt\n"
            "190g plain flour\n"
            "100g walnuts, roughly chopped"
        ),
        "directions": (
            "Preheat oven to 175°C. Grease a 9x5 inch loaf tin.\n"
            "Mash bananas in a large bowl until smooth.\n"
            "Stir in melted butter.\n"
            "Mix in sugar, beaten egg, and vanilla.\n"
            "Sprinkle in baking soda and salt. Stir to combine.\n"
            "Fold in flour until just incorporated. Do not over-mix.\n"
            "Fold in walnuts.\n"
            "Pour batter into prepared tin. Bake 55-65 minutes until a skewer comes out clean.\n"
            "Cool in tin 10 minutes, then turn out onto a wire rack."
        ),
    },
]


class Command(BaseCommand):
    help = "Load sample recipes for local development and demos."

    def handle(self, *args, **options):
        from recipes.models import Recipe, Tag

        self.stdout.write("Loading sample tags...")
        tag_objects = {}
        for tag_name in SAMPLE_TAGS:
            tag, created = Tag.objects.get_or_create(
                name=tag_name,
                defaults={'slug': slugify(tag_name)},
            )
            tag_objects[tag_name] = tag
            if created:
                self.stdout.write(f"  Created tag: {tag_name}")

        self.stdout.write("Loading sample recipes...")
        for data in SAMPLE_RECIPES:
            recipe, created = Recipe.objects.get_or_create(
                slug=slugify(data["title"]),
                defaults={
                    "title": data["title"],
                    "image_url": data["image_url"],
                    "ingredients": data["ingredients"],
                    "directions": data["directions"],
                },
            )
            if created:
                for tag_name in data["tags"]:
                    recipe.tags.add(tag_objects[tag_name])
                self.stdout.write(f"  Created recipe: {data['title']}")
            else:
                self.stdout.write(f"  Already exists: {data['title']}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {len(SAMPLE_RECIPES)} recipes and {len(SAMPLE_TAGS)} tags loaded."
        ))
