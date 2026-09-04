with open("src/index.css", "r") as f:
    content = f.read()

content = content.replace(":root {", ":root {\n  color-scheme: dark;")
content = content.replace("[data-theme=\"light\"] {", "[data-theme=\"light\"] {\n  color-scheme: light;")

with open("src/index.css", "w") as f:
    f.write(content)
