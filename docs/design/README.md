# Design

Reference: https://www.figma.com/design/b79P5kNBD1ntjyoyAjER0P/mosAIc?node-id=20-2

The five approved desktop screens are implemented with responsive layouts, local Figma SVG assets, and local Inter/Geist fonts. Dynamic images, attribution, recipe metadata and readiness come from the backend. Unsupported permission claims and invented creator handles from the initial wireframes are replaced with verified API values or explicit unknown states.

Inter and Geist redistribution licenses are included as `apps/web/public/assets/OFL-Inter.txt` and `OFL-Geist.txt` (Google Fonts / SIL Open Font License).

Changes from the Figma file: the Community page was dropped (it showed the same list as Discover), the recipe page shows the creator's public prompt instead of a "kept private" badge, and the creator panel links to the original post and, once verified, the creator's Instagram.
