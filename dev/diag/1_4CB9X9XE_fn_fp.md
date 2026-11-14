# 4CB9X9XE baseline (dev_baseline run): false negatives and false positives

gold edges 48, predicted edges 54, FN 47, FP 53

entity_agree (the loose gate) needs: both nodes have a taxon -> shared NCBITaxon id or shared (genus,epithet); else the free-text entity must have Jaccard >= 0.5.

## FALSE NEGATIVES (all)

1. [4CB9X9XE-e01] no loose match (the pair of entities was not found)
   gold: [Increased] seed production of planted prairie species --associated_with--> [Increased] rodent consumption of planted prairie plants
   best candidate (sim 0.55): [Increased] seed production of Elymus canadensis --associated_with--> [Increased] consumption of Elymus canadensis
   sentence: The exceptions were August–September, when planted prairie species accounted for 87% of plants consumed and coincided with their peak seed production.
2. [4CB9X9XE-e02] no loose match (the pair of entities was not found)
   gold: [Decreased] availability of native prairie seed --causes--> [Decreased] rodent consumption of native prairie seed
   best candidate (sim 0.5275000000000001): [Increased] seed availability --causes--> [Increased] consumption of Elymus canadensis
   sentence: Cafeteria trials suggested diet seasonality to be explained by food limitation – native prairie seeds were consumed year-round when made available.
3. [4CB9X9XE-e03] no loose match (the pair of entities was not found)
   gold: [Occurred] Rodent consumption of non-planted oldfield plants --contributes_to--> [Ongoing] persistence of rodent populations at normal to high levels
   best candidate (sim 0.4015000000000001): [Present] Presence of abundance of oldfield plants --contributes_to--> [Increased] diet composition of Peromyscus maniculatus
   sentence: Non-targeted oldfield species thus appeared to be of sufficient quality to support rodent populations (peaking at 23 individuals ha<sup>1</sup> in summer), but without rescuing rarer prairie species from targeted granivory and resulting in reduced prairie diversity outside of experimental exclosures.
4. [4CB9X9XE-e04] no loose match (the pair of entities was not found)
   gold: [Occurred] Rodent consumption of non-planted oldfield plants --prevents--> [Occurred] Rodent granivory on planted prairie species (NULL)
   best candidate (sim 0.37): [Increased] density of Peromyscus maniculatus --causes--> Seed removal of Elymus canadensis (NULL)
   sentence: Non-targeted oldfield species thus appeared to be of sufficient quality to support rodent populations (peaking at 23 individuals ha<sup>1</sup> in summer), but without rescuing rarer prairie species from targeted granivory and resulting in reduced prairie diversity outside of experimental exclosures.
5. [4CB9X9XE-e05] no loose match (the pair of entities was not found)
   gold: [Increased] rodent granivory on planted prairie species --causes--> [Decreased] species richness of planted prairie species
   best candidate (sim 0.58375): [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] species richness of planted native species
   sentence: Non-targeted oldfield species thus appeared to be of sufficient quality to support rodent populations (peaking at 23 individuals ha<sup>1</sup> in summer), but without rescuing rarer prairie species from targeted granivory and resulting in reduced prairie diversity outside of experimental exclosures.
6. [4CB9X9XE-e06] no loose match (the pair of entities was not found)
   gold: [Increased] rodent granivory on planted prairie species --contributes_to--> [Increased] establishment of introduced oldfield species
   best candidate (sim 0.5275000000000001): [Increased] consumption of native seed of Peromyscus maniculatus --contributes_to--> [Increased] establishment of oldfield species
   sentence: Our work illustrates how anthropogenic-based changes to producer communities may affect feeding pathways in grassland food webs, potentially facilitating establishment by non-target species via indirect consumer effects that can be difficult to detect.
7. [4CB9X9XE-e07] no loose match (the pair of entities was not found)
   gold: [Present] Presence of native rodents --causes--> [Decreased] restoration success of planted tallgrass prairie
   best candidate (sim 0.595): [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] restoration success
   sentence: These findings suggest that rodents may reduce the restoration success of tallgrass prairie in our region, with some planted species likely to suffer future recruitment difficulties due to granivory.
8. [4CB9X9XE-e08] no loose match (the pair of entities was not found)
   gold: [Increased] rodent granivory on planted prairie species --causes--> [Decreased] recruitment of planted prairie species
   best candidate (sim 0.44875): [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] species richness of planted native species
   sentence: These findings suggest that rodents may reduce the restoration success of tallgrass prairie in our region, with some planted species likely to suffer future recruitment difficulties due to granivory.
9. [4CB9X9XE-e09] no loose match (the pair of entities was not found)
   gold: [Present] Late-summer period (August-September) --associated_with--> [Increased] rodent consumption of planted prairie plants
   best candidate (sim 0.31375000000000003): [Present] Presence of abundance of oldfield plants --contributes_to--> [Increased] diet composition of Peromyscus maniculatus
   sentence: We detected pronounced seasonal diet trends with the monthly DNA sampling, with non-targeted oldfield species constituting most of the diet annually except in late summer when rodents preferentially consumed subsets of native prairie plants presumably as seed ( $F_{4,11} = 17.2$ , P < 0.0001).
10. [4CB9X9XE-e11] no loose match (the pair of entities was not found)
   gold: [Increased] rodent population density --correlated_with--> [Increased] number of oldfield species consumed by rodents
   best candidate (sim 0.45999999999999996): [Increased] density of Peromyscus maniculatus --correlated_with--> [Increased] consumption of oldfield species
   sentence: Rodent density per month and numbers of oldfield species consumed per month were positively correlated ( $R^2 = 0.166$ , P = 0.041), while no relationship was detectable between rodent density and native plant consumption $(R^2 = 0.0786,$ P = 0.43).
11. [4CB9X9XE-e12] no loose match (the pair of entities was not found)
   gold: [Increased] rodent population density --correlated_with--> [Increased] rodent consumption of planted prairie plants (NULL)
   best candidate (sim 0.4760714285714286): [Increased] density of Peromyscus maniculatus --causes--> Native plant consumption (NULL)
   sentence: Rodent density per month and numbers of oldfield species consumed per month were positively correlated ( $R^2 = 0.166$ , P = 0.041), while no relationship was detectable between rodent density and native plant consumption $(R^2 = 0.0786,$ P = 0.43).
12. [4CB9X9XE-e13] no loose match (the pair of entities was not found)
   gold: Month of the year --associated_with--> Rodent seed species preference (NULL)
   best candidate (sim 0.23500000000000001): [Increased] density of Peromyscus maniculatus --causes--> Native plant consumption (NULL)
   sentence: Seed removals from the cafeteria trials occurred in every month, with no seasonal variation in species preference based on order of removal from the feeding stations
13. [4CB9X9XE-e14] no loose match (the pair of entities was not found)
   gold: [Increased] rodent population density --associated_with--> [Increased] removal of Andropogon gerardii seed
   best candidate (sim 0.64): [Increased] density of Peromyscus maniculatus --causes--> [Increased] consumption of Andropogon gerardii
   sentence: Andropogon gerardii, which was ignored most months, was consumed during June and July when rodent densities were highest
14. [4CB9X9XE-e15] no loose match (the pair of entities was not found)
   gold: [Increased] seed production of planted prairie species --associated_with--> [Decreased] seed removal from cafeteria stations
   best candidate (sim 0.55): [Increased] seed production of Elymus canadensis --associated_with--> [Decreased] consumption of Peromyscus maniculatus
   sentence: There were variations among months in the amount of seed taken - removals from the cafeteria stations dropped significantly in late summer $(F_{11,156} = 2.013, P = 0.0305)$ Tukey's HSD), which corresponded with the peak in seed production in the field, when the planted species were most prevalent in DNA scat, but also when rodent captures declined (Fig. 4).
15. [4CB9X9XE-e16] no loose match (the pair of entities was not found)
   gold: [Decreased] rodent population density --associated_with--> [Decreased] seed removal from cafeteria stations
   best candidate (sim 0.29125): [Decreased] density of Peromyscus maniculatus --associated_with--> [Increased] seed production of Elymus canadensis
   sentence: There were variations among months in the amount of seed taken - removals from the cafeteria stations dropped significantly in late summer $(F_{11,156} = 2.013, P = 0.0305)$ Tukey's HSD), which corresponded with the peak in seed production in the field, when the planted species were most prevalent in DNA scat, but also when rodent captures declined (Fig. 4).
16. [4CB9X9XE-e17] no loose match (the pair of entities was not found)
   gold: [Increased] rodent population density --correlated_with--> [Increased] removal of preferred seed from cafeteria stations (NULL)
   best candidate (sim 0.40937500000000004): [Increased] density of Peromyscus maniculatus --causes--> Native plant consumption (NULL)
   sentence: There was no correlation between rodent densities by month and the removal of preferred seed from the feeding stations - removal was similarly high in summer during the population peak and when rodent numbers were low in winter $(R^2 = 0.210,$ P = 0.137).
17. [4CB9X9XE-e18] right entities, object attribute differs (similarity 0.00)
   gold: [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   best candidate (sim 0.0): [Increased] population density of Peromyscus maniculatus --causes--> [Increased] granivory of Peromyscus maniculatus
   sentence: Seedling herbivory was only observed after all preferred seeds were taken, and only for two Asteraceae forb species out of the seven planted species ( $F_{3,7} = 16.6$ , P < 0.0001).
18. [4CB9X9XE-e19] right entities, but one side is a null result and the other a positive claim (null flags disagree)
   gold: [Present] Presence of Peromyscus maniculatus in captive feeding trials --causes--> [Occurred] Herbivory on adult native prairie plants (NULL)
   best candidate (sim 0.4600000000000001): [Increased] density of Peromyscus maniculatus --causes--> Native plant consumption (NULL)
   sentence: We detected no consumption of plant parts of adult native species in our captive feeding trials.
19. [4CB9X9XE-e20] no loose match (the pair of entities was not found)
   gold: [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] abundance of planted native seedlings
   best candidate (sim 0.505): [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> [Increased] abundance of planted native seedlings
   sentence: The exclosed plots had twice the abundance of planted native seedlings ( $F_{1,5} = 5.92$ , P = 0.0196) and significantly higher richness of planted species ( $F_{1.5} = 13.8$ , P < 0.001) than areas lacking protection from small mammals (Figs 2 and S1).
20. [4CB9X9XE-e21] no loose match (the pair of entities was not found)
   gold: [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] species richness of planted prairie species
   best candidate (sim 0.58375): [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> [Increased] richness of planted native species
   sentence: The exclosed plots had twice the abundance of planted native seedlings ( $F_{1,5} = 5.92$ , P = 0.0196) and significantly higher richness of planted species ( $F_{1.5} = 13.8$ , P < 0.001) than areas lacking protection from small mammals (Figs 2 and S1).
21. [4CB9X9XE-e22] no loose match (the pair of entities was not found)
   gold: [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   best candidate (sim 0.505): [Increased] seed production of Elymus canadensis --associated_with--> [Increased] consumption of Elymus canadensis
   sentence: Most notable was E. canadensis (C3 grass), with 51 individuals observed in the exclosures, but none in open areas.
22. [4CB9X9XE-e23] no loose match (the pair of entities was not found)
   gold: [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] recruitment of oldfield plants (NULL)
   best candidate (sim 0.5275000000000001): [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> Recruitment of oldfield plants (NULL)
   sentence: There were no recruitment differences for oldfield plants inside vs. outside the exclosures.
23. [4CB9X9XE-e24] no loose match (the pair of entities was not found)
   gold: [Occurred] Mowing (experimental defoliation) --associated_with--> [Decreased] species richness of planted prairie species
   best candidate (sim 0.5425): Mowing --causes--> [Increased] detection of native seed of Peromyscus maniculatus
   sentence: The richness of planted prairie species outside the cages was especially low in seeded plots that were experimentally defoliated with mowing (Fig. S1), suggesting that small mammals were more able to detect native seed in these
24. [4CB9X9XE-e25] no loose match (the pair of entities was not found)
   gold: [Occurred] Mowing (experimental defoliation) --contributes_to--> [Increased] seed detection by small mammals
   best candidate (sim 0.685): Mowing --causes--> [Increased] detection of native seed of Peromyscus maniculatus
   sentence: The richness of planted prairie species outside the cages was especially low in seeded plots that were experimentally defoliated with mowing (Fig. S1), suggesting that small mammals were more able to detect native seed in these
25. [4CB9X9XE-e26] no loose match (the pair of entities was not found)
   gold: [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] recruitment of Rudbeckia hirta (NULL)
   best candidate (sim 0.41500000000000004): [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> Recruitment of oldfield plants (NULL)
   sentence: Rudbeckia hirta is a native prairie forb with tiny seeds that does not suffer significant rodent granivory (see Fig. S1) and recruited in large numbers inside and outside of the exclosures.
26. [4CB9X9XE-e27] no loose match (the pair of entities was not found)
   gold: [Increased] seed production of planted prairie species --associated_with--> [Increased] rodent consumption of planted prairie plants
   best candidate (sim 0.55): [Increased] seed production of Elymus canadensis --associated_with--> [Increased] consumption of Elymus canadensis
   sentence: We mostly observed the first outcome, with native consumers showing preferences for subsets of planted native prairie species despite their rarity regionally, and almost exclusively at times of peak seed output.
27. [4CB9X9XE-e28] no loose match (the pair of entities was not found)
   gold: [Decreased] availability of native prairie seed --causes--> [Decreased] rodent consumption of native prairie seed
   best candidate (sim 0.5275000000000001): [Increased] seed availability --causes--> [Increased] consumption of Elymus canadensis
   sentence: The consumption of seeds of these plants were observed year-round in the monthly cafeteria trials, with same subset of species taken consistently and in the same order, suggesting that consumption levels in this system could be determined more by seed availability than by changes in consumer preference by season (i.e. seed consumption appears to end in late fall because of food limitation, rather than switching to different species).
28. [4CB9X9XE-e29] no loose match (the pair of entities was not found)
   gold: [Present] Presence of introduced oldfield plant species --contributes_to--> [Ongoing] persistence of rodent populations at normal to high levels
   best candidate (sim 0.39250000000000007): [Present] Presence of abundance of oldfield species --contributes_to--> [Increased] population density of Peromyscus maniculatus
   sentence: However, with our observed deer mouse population densities at normal to high levels for southern Canada (Davidson & Morris 2001), the implication is that these introduced species provide sufficient resources to maintain rodent populations in this system.
29. [4CB9X9XE-e30] no loose match (the pair of entities was not found)
   gold: [Ongoing] persistence of rodent populations at normal to high levels --causes--> [Increased] rodent granivory on planted prairie species
   best candidate (sim 0.28): [Present] Presence of abundance of oldfield species --contributes_to--> [Increased] population density of Peromyscus maniculatus
   sentence: If true, the net effect is likely twofold: normal to high population levels of rodents being maintained, which in turn exerts intense granivore pressure thereby inhibiting recruitment by some native prairie plants.
30. [4CB9X9XE-e31] no loose match (the pair of entities was not found)
   gold: [Increased] rodent granivory on planted prairie species --causes--> [Decreased] recruitment of planted prairie species
   best candidate (sim 0.44875): [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] species richness of planted native species
   sentence: If true, the net effect is likely twofold: normal to high population levels of rodents being maintained, which in turn exerts intense granivore pressure thereby inhibiting recruitment by some native prairie plants.
31. [4CB9X9XE-e32] no loose match (the pair of entities was not found)
   gold: [Present] Presence of introduced oldfield plant species --contributes_to--> [Decreased] recruitment of planted prairie species
   best candidate (sim 0.5275): [Present] Presence of abundance of oldfield species --disrupts--> [Decreased] recruitment of Elymus canadensis
   sentence: If true, the net effect is likely twofold: normal to high population levels of rodents being maintained, which in turn exerts intense granivore pressure thereby inhibiting recruitment by some native prairie plants.
32. [4CB9X9XE-e33] no loose match (the pair of entities was not found)
   gold: [Increased] rodent granivory on planted prairie species --contributes_to--> [Decreased] restoration success of planted tallgrass prairie
   best candidate (sim 0.64): [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] restoration success
   sentence: This targeted granviory may present a substantial challenge for the restoration success of planted high-diversity prairie, if subsets of species are preferentially consumed by native rodents once the prairie reaches canopy closure and rodent populations become established.
33. [4CB9X9XE-e34] no loose match (the pair of entities was not found)
   gold: [Absent] Absence of rodents --contributes_to--> [Increased] initial establishment of prairie plantings
   best candidate (sim 0.35875): [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> [Increased] richness of planted native species
   sentence: This creates a subtle but difficult restoration challenge – prairie plantings on unvegetated fields may initially succeed because rodents are absent (see Germain et al. 2013), but future recruitment may be significantly constrained for some species.
34. [4CB9X9XE-e35] no loose match (the pair of entities was not found)
   gold: [Present] Presence of native rodents --causes--> [Decreased] recruitment of planted prairie species
   best candidate (sim 0.41500000000000004): [Present] Presence of abundance of oldfield species --disrupts--> [Decreased] recruitment of Elymus canadensis
   sentence: This creates a subtle but difficult restoration challenge – prairie plantings on unvegetated fields may initially succeed because rodents are absent (see Germain et al. 2013), but future recruitment may be significantly constrained for some species.
35. [4CB9X9XE-e36] no loose match (the pair of entities was not found)
   gold: [Increased] rodent granivory on planted prairie species --contributes_to--> [Increased] establishment of introduced oldfield species
   best candidate (sim 0.5275000000000001): [Increased] consumption of native seed of Peromyscus maniculatus --contributes_to--> [Increased] establishment of oldfield species
   sentence: We observed high consumption levels of native seed by native consumers, suggesting the possible facilitation of introduced species initially
36. [4CB9X9XE-e37] no loose match (the pair of entities was not found)
   gold: [Occurred] Rodent consumption of non-planted oldfield plants --causes--> [Decreased] expansion rate of oldfield plant species
   best candidate (sim 0.35875): [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] species richness of planted native species
   sentence: One implication is the expansion rate of these plant species, including some aggressive invasives, could even be curtailed by rodent consumers, compared to what it would be in their absence
37. [4CB9X9XE-e38] no loose match (the pair of entities was not found)
   gold: [Increased] rodent population density --associated_with--> [Increased] breadth of rodent diet
   best candidate (sim 0.41500000000000004): [Increased] population density of Peromyscus maniculatus --causes--> [Increased] granivory of Peromyscus maniculatus
   sentence: For example, at peak rodent population density in July we observed the widest range of plant species in the rodent diet, including non-native and potentially invasive trees, grasses, and forbs, as well as the most rapid depletion of seed from the widest range of plants in the cafeteria trials
38. [4CB9X9XE-e39] no loose match (the pair of entities was not found)
   gold: [Increased] rodent population density --associated_with--> [Increased] Faster depletion of seed from cafeteria stations
   best candidate (sim 0.4375): [Increased] density of Peromyscus maniculatus --contributes_to--> [Increased] seed depletion of Peromyscus maniculatus
   sentence: For example, at peak rodent population density in July we observed the widest range of plant species in the rodent diet, including non-native and potentially invasive trees, grasses, and forbs, as well as the most rapid depletion of seed from the widest range of plants in the cafeteria trials
39. [4CB9X9XE-e40] no loose match (the pair of entities was not found)
   gold: [Increased] Mustela erminea abundance --contributes_to--> [Decreased] rodent population density
   best candidate (sim 0.5725): [Increased] predation of Mustela erminea --contributes_to--> [Decreased] density of Peromyscus maniculatus
   sentence: There could also be a predatory influence of weasels, which were trapped in highest numbers in late summer.
40. [4CB9X9XE-e41] no loose match (the pair of entities was not found)
   gold: [Decreased] rodent population density --associated_with--> [Decreased] seed removal from cafeteria stations (NULL)
   best candidate (sim 0.319375): [Increased] density of Peromyscus maniculatus --causes--> Native plant consumption (NULL)
   sentence: although the reduced rodent population size was not associated with changes in the magnitude of seed removal from the cafeteria trials.
41. [4CB9X9XE-e42] no loose match (the pair of entities was not found)
   gold: [Occurred] Rodent consumption of non-planted oldfield plants --contributes_to--> [Ongoing] persistence of rodent populations at normal to high levels
   best candidate (sim 0.4015000000000001): [Present] Presence of abundance of oldfield plants --contributes_to--> [Increased] diet composition of Peromyscus maniculatus
   sentence: The consumption of non-targeted oldfield species appears sufficient to maintain rodent populations at high levels (Davidson & Morris 2001).
42. [4CB9X9XE-e43] no loose match (the pair of entities was not found)
   gold: [Occurred] Rodent consumption of non-planted oldfield plants --prevents--> [Occurred] Rodent granivory on planted prairie species (NULL)
   best candidate (sim 0.37): [Increased] density of Peromyscus maniculatus --causes--> Seed removal of Elymus canadensis (NULL)
   sentence: However, this seems to be insufficient to shelter rarer prairie species from targeted granivory, which in turn may hamper their persistence.
43. [4CB9X9XE-e44] no loose match (the pair of entities was not found)
   gold: [Increased] rodent granivory on planted prairie species --causes--> [Decreased] persistence of rare prairie species
   best candidate (sim 0.44875): [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] species richness of planted native species
   sentence: However, this seems to be insufficient to shelter rarer prairie species from targeted granivory, which in turn may hamper their persistence.
44. [4CB9X9XE-e45] no loose match (the pair of entities was not found)
   gold: [Introduced] Seed addition of prairie species --contributes_to--> [Increased] persistence of rare prairie species
   best candidate (sim 0.44875): [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> [Increased] richness of planted native species
   sentence: It also suggests that some prairie plants, already regionally rare, may be locked in an extinction debt that may be difficult to solve with seed additions alone, with little consumption detected on adults or seedlings (Germain et al. 2013) but intense granivory that suggest future recruitment difficulties (Bricker, Pearson & Maron 2010).
45. [4CB9X9XE-e46] no loose match (the pair of entities was not found)
   gold: [Increased] rodent granivory on planted prairie species --causes--> [Decreased] recruitment of planted prairie species
   best candidate (sim 0.44875): [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] species richness of planted native species
   sentence: It also suggests that some prairie plants, already regionally rare, may be locked in an extinction debt that may be difficult to solve with seed additions alone, with little consumption detected on adults or seedlings (Germain et al. 2013) but intense granivory that suggest future recruitment difficulties (Bricker, Pearson & Maron 2010).
46. [4CB9X9XE-e47] no loose match (the pair of entities was not found)
   gold: [Introduced] Restoration of habitat features favouring rodent predators --contributes_to--> [Increased] abundance of rodent predators
   best candidate (sim 0.41500000000000004): [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> [Increased] abundance of planted native seedlings
   sentence: It may also be important to consider restoring habitat features that favor rodent predators such as raptors and small mammalian carnivores such as badgers (Taxidea taxus), although these species tend to be even rarer and more at-risk in grasslands than the plants they may indirectly protect
47. [4CB9X9XE-e48] no loose match (the pair of entities was not found)
   gold: [Increased] abundance of rodent predators --contributes_to--> [Increased] persistence of rare prairie species
   best candidate (sim 0.44875): [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> [Increased] richness of planted native species
   sentence: It may also be important to consider restoring habitat features that favor rodent predators such as raptors and small mammalian carnivores such as badgers (Taxidea taxus), although these species tend to be even rarer and more at-risk in grasslands than the plants they may indirectly protect

## FALSE POSITIVES (all)

1. [4CB9X9XE-e1] no loose match (the pair of entities was not found)
   ours: [Increased] seed production of Elymus canadensis --associated_with--> [Increased] consumption of Elymus canadensis
   nearest gold (sim 0.55): [Increased] seed production of planted prairie species --associated_with--> [Increased] rodent consumption of planted prairie plants
   sentence: The exceptions were August–September, when planted prairie species accounted for 87% of plants consumed and coincided with their peak seed production.
2. [4CB9X9XE-e2] no loose match (the pair of entities was not found)
   ours: [Increased] seed production of Elymus canadensis --associated_with--> [Increased] consumption of Lespedeza capitata
   nearest gold (sim 0.55): [Increased] seed production of planted prairie species --associated_with--> [Increased] rodent consumption of planted prairie plants
   sentence: The exceptions were August–September, when planted prairie species accounted for 87% of plants consumed and coincided with their peak seed production.
3. [4CB9X9XE-e3] no loose match (the pair of entities was not found)
   ours: Food limitation --causes--> [Increased] consumption of Elymus canadensis
   nearest gold (sim 0.45999999999999996): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   sentence: Cafeteria trials suggested diet seasonality to be explained by food limitation – native prairie seeds were consumed year-round when made available.
4. [4CB9X9XE-e4] no loose match (the pair of entities was not found)
   ours: Food limitation --causes--> [Increased] consumption of Lespedeza capitata
   nearest gold (sim 0.3025): [Increased] rodent population density --associated_with--> [Increased] removal of Andropogon gerardii seed
   sentence: Cafeteria trials suggested diet seasonality to be explained by food limitation – native prairie seeds were consumed year-round when made available.
5. [4CB9X9XE-e5] no loose match (the pair of entities was not found)
   ours: [Present] Presence of abundance of oldfield species --contributes_to--> [Increased] population density of Peromyscus maniculatus
   nearest gold (sim 0.55): [Increased] Mustela erminea abundance --associated_with--> [Decreased] Peromyscus maniculatus population size
   sentence: Non-targeted oldfield species thus appeared to be of sufficient quality to support rodent populations (peaking at 23 individuals ha1 in summer), but without rescuing rarer prairie species from targeted granivory and resulting in reduced prairie diversity outside of experimental exclosures.
6. [4CB9X9XE-e6] no loose match (the pair of entities was not found)
   ours: [Present] Presence of abundance of oldfield species --contributes_to--> [Increased] population density of Zapus hudsonius
   nearest gold (sim 0.41500000000000004): [Increased] Mustela erminea abundance --contributes_to--> [Decreased] rodent population density
   sentence: Non-targeted oldfield species thus appeared to be of sufficient quality to support rodent populations (peaking at 23 individuals ha1 in summer), but without rescuing rarer prairie species from targeted granivory and resulting in reduced prairie diversity outside of experimental exclosures.
7. [4CB9X9XE-e7] no loose match (the pair of entities was not found)
   ours: [Present] Presence of abundance of oldfield species --disrupts--> [Decreased] recruitment of Elymus canadensis
   nearest gold (sim 0.5275): [Present] Presence of introduced oldfield plant species --contributes_to--> [Decreased] recruitment of planted prairie species
   sentence: Non-targeted oldfield species thus appeared to be of sufficient quality to support rodent populations (peaking at 23 individuals ha1 in summer), but without rescuing rarer prairie species from targeted granivory and resulting in reduced prairie diversity outside of experimental exclosures.
8. [4CB9X9XE-e8] no loose match (the pair of entities was not found)
   ours: [Present] Presence of abundance of oldfield species --disrupts--> [Decreased] recruitment of Lespedeza capitata
   nearest gold (sim 0.5275): [Present] Presence of introduced oldfield plant species --contributes_to--> [Decreased] recruitment of planted prairie species
   sentence: Non-targeted oldfield species thus appeared to be of sufficient quality to support rodent populations (peaking at 23 individuals ha1 in summer), but without rescuing rarer prairie species from targeted granivory and resulting in reduced prairie diversity outside of experimental exclosures.
9. [4CB9X9XE-e9] no loose match (the pair of entities was not found)
   ours: [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] restoration success
   nearest gold (sim 0.64): [Increased] rodent granivory on planted prairie species --contributes_to--> [Decreased] restoration success of planted tallgrass prairie
   sentence: These findings suggest that rodents may reduce the restoration success of tallgrass prairie in our region, with some planted species likely to suffer future recruitment difficulties due to granivory.
10. [4CB9X9XE-e10] no loose match (the pair of entities was not found)
   ours: [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] recruitment of Elymus canadensis
   nearest gold (sim 0.41500000000000004): [Increased] rodent granivory on planted prairie species --causes--> [Decreased] recruitment of planted prairie species
   sentence: These findings suggest that rodents may reduce the restoration success of tallgrass prairie in our region, with some planted species likely to suffer future recruitment difficulties due to granivory.
11. [4CB9X9XE-e11] no loose match (the pair of entities was not found)
   ours: [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] recruitment of Lespedeza capitata
   nearest gold (sim 0.41500000000000004): [Increased] rodent granivory on planted prairie species --causes--> [Decreased] recruitment of planted prairie species
   sentence: These findings suggest that rodents may reduce the restoration success of tallgrass prairie in our region, with some planted species likely to suffer future recruitment difficulties due to granivory.
12. [4CB9X9XE-e12] no loose match (the pair of entities was not found)
   ours: Late_spring of season --causes--> [Increased] consumption of Elymus canadensis
   nearest gold (sim 0.45999999999999996): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   sentence: We detected pronounced seasonal diet trends with the monthly DNA sampling, with non-targeted oldfield species constituting most of the diet annually except in late summer when rodents preferentially consumed subsets of native prairie plants presumably as seed ( F4,11 = 17.2 , P < 0.0001).
13. [4CB9X9XE-e13] no loose match (the pair of entities was not found)
   ours: Late_spring of season --causes--> [Increased] consumption of Lespedeza capitata
   nearest gold (sim 0.3025): [Increased] rodent population density --associated_with--> [Increased] removal of Andropogon gerardii seed
   sentence: We detected pronounced seasonal diet trends with the monthly DNA sampling, with non-targeted oldfield species constituting most of the diet annually except in late summer when rodents preferentially consumed subsets of native prairie plants presumably as seed ( F4,11 = 17.2 , P < 0.0001).
14. [4CB9X9XE-e15] no loose match (the pair of entities was not found)
   ours: [Increased] density of Peromyscus maniculatus --correlated_with--> [Increased] consumption of oldfield species
   nearest gold (sim 0.45999999999999996): [Increased] rodent population density --correlated_with--> [Increased] number of oldfield species consumed by rodents
   sentence: Rodent density per month and numbers of oldfield species consumed per month were positively correlated ( R2 = 0.166 , P = 0.041), while no relationship was detectable between rodent density and native plant consumption (R2 = 0.0786, P = 0.43).
15. [4CB9X9XE-e16] no loose match (the pair of entities was not found)
   ours: [Increased] density of Peromyscus maniculatus --causes--> Native plant consumption (NULL)
   nearest gold (sim 0.4760714285714286): [Increased] rodent population density --correlated_with--> [Increased] rodent consumption of planted prairie plants (NULL)
   sentence: Rodent density per month and numbers of oldfield species consumed per month were positively correlated ( R2 = 0.166 , P = 0.041), while no relationship was detectable between rodent density and native plant consumption (R2 = 0.0786, P = 0.43).
16. [4CB9X9XE-e17] no loose match (the pair of entities was not found)
   ours: [Absent] Absence of consumption of Elymus canadensis --causes--> [Absent] Absence of seed caching of Elymus canadensis
   nearest gold (sim 0.325): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   sentence: This result indicates that rodents are not seed caching native prairie plants.
17. [4CB9X9XE-e18] no loose match (the pair of entities was not found)
   ours: [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] species richness of planted native species
   nearest gold (sim 0.58375): [Increased] rodent granivory on planted prairie species --causes--> [Decreased] species richness of planted prairie species
   sentence: Seed removals from the cafeteria trials occurred in every month, with no seasonal variation in species preference based on order of removal from the feeding stations (i.e. the same subset of species were always consumed first areas – species richness was reduced on average 46 9 compared to the same treatment in the cages (F1,47 = 723, P = 00104 Tukey's HSD).
18. [4CB9X9XE-e19] no loose match (the pair of entities was not found)
   ours: [Occurred] Occurrence of feeding trial of Peromyscus maniculatus --causes--> [Increased] consumption of Elymus canadensis
   nearest gold (sim 0.45999999999999996): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   sentence: In all months, rodents targeted the same four species: a tree (A. saccarhum), two large-seeded native forbs (H. divaricatus and L. capitata) and a native C3 grass (E. canadensis).
19. [4CB9X9XE-e20] no loose match (the pair of entities was not found)
   ours: [Occurred] Occurrence of feeding trial of Peromyscus maniculatus --causes--> [Increased] consumption of Lespedeza capitata
   nearest gold (sim 0.41500000000000004): [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   sentence: In all months, rodents targeted the same four species: a tree (A. saccarhum), two large-seeded native forbs (H. divaricatus and L. capitata) and a native C3 grass (E. canadensis).
20. [4CB9X9XE-e21] no loose match (the pair of entities was not found)
   ours: [Occurred] Occurrence of feeding trial of Peromyscus maniculatus --causes--> [Increased] consumption of Helianthus divaricatus
   nearest gold (sim 0.41500000000000004): [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   sentence: In all months, rodents targeted the same four species: a tree (A. saccarhum), two large-seeded native forbs (H. divaricatus and L. capitata) and a native C3 grass (E. canadensis).
21. [4CB9X9XE-e22] no loose match (the pair of entities was not found)
   ours: [Occurred] Occurrence of feeding trial of Peromyscus maniculatus --causes--> [Decreased] consumption of Andropogon gerardii
   nearest gold (sim 0.4375): [Increased] rodent population density --associated_with--> [Increased] removal of Andropogon gerardii seed
   sentence: In all months, rodents targeted the same four species: a tree (A. saccarhum), two large-seeded native forbs (H. divaricatus and L. capitata) and a native C3 grass (E. canadensis).
22. [4CB9X9XE-e23] no loose match (the pair of entities was not found)
   ours: [Increased] density of Peromyscus maniculatus --causes--> [Increased] consumption of Andropogon gerardii
   nearest gold (sim 0.64): [Increased] rodent population density --associated_with--> [Increased] removal of Andropogon gerardii seed
   sentence: Andropogon gerardii, which was ignored most months, was consumed during June and July when rodent densities were highest, while the remaining two species (B. kalmii and R. hirta) were almost never taken (F11,156 = 2.039, P = 0.0281 Tukey's HSD) .
23. [4CB9X9XE-e24] no loose match (the pair of entities was not found)
   ours: [Increased] seed production of Elymus canadensis --associated_with--> [Decreased] consumption of Peromyscus maniculatus
   nearest gold (sim 0.55): [Increased] seed production of planted prairie species --associated_with--> [Decreased] seed removal from cafeteria stations
   sentence: There were variations among months in the amount of seed taken - removals from the cafeteria stations dropped significantly in late summer (F11,156 = 2.013, P = 0.0305) Tukey's HSD), which corresponded with the peak in seed production in the field, when the planted species were most prevalent in DNA scat, but also when rodent captures declined (Fig. 4).
24. [4CB9X9XE-e25] no loose match (the pair of entities was not found)
   ours: [Occurred] Occurrence of feeding trial of Peromyscus maniculatus --causes--> [Increased] consumption of Elymus canadensis
   nearest gold (sim 0.45999999999999996): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   sentence: The captive feeding trials demonstrated the identical order of seed consumption as observed in the field, with preferences for the same four species (Fig. 3, F3.7 = 117 , P < 0.0001, Tukey's HSD).
25. [4CB9X9XE-e26] no loose match (the pair of entities was not found)
   ours: [Occurred] Occurrence of feeding trial of Peromyscus maniculatus --causes--> [Increased] consumption of Lespedeza capitata
   nearest gold (sim 0.41500000000000004): [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   sentence: The captive feeding trials demonstrated the identical order of seed consumption as observed in the field, with preferences for the same four species (Fig. 3, F3.7 = 117 , P < 0.0001, Tukey's HSD).
26. [4CB9X9XE-e27] no loose match (the pair of entities was not found)
   ours: [Occurred] Occurrence of feeding trial of Peromyscus maniculatus --causes--> [Increased] consumption of Helianthus divaricatus
   nearest gold (sim 0.41500000000000004): [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   sentence: The captive feeding trials demonstrated the identical order of seed consumption as observed in the field, with preferences for the same four species (Fig. 3, F3.7 = 117 , P < 0.0001, Tukey's HSD).
27. [4CB9X9XE-e28] no loose match (the pair of entities was not found)
   ours: [Occurred] Occurrence of feeding trial of Peromyscus maniculatus --causes--> [Decreased] consumption of Andropogon gerardii
   nearest gold (sim 0.4375): [Increased] rodent population density --associated_with--> [Increased] removal of Andropogon gerardii seed
   sentence: The captive feeding trials demonstrated the identical order of seed consumption as observed in the field, with preferences for the same four species (Fig. 3, F3.7 = 117 , P < 0.0001, Tukey's HSD).
28. [4CB9X9XE-e29] no loose match (the pair of entities was not found)
   ours: [Increased] seed consumption of Elymus canadensis --contributes_to--> [Increased] seedling herbivory of Elymus canadensis
   nearest gold (sim 0.505): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   sentence: Seedling herbivory was only observed after all preferred seeds were taken, and only for two Asteraceae forb species out of the seven planted species ( F3,7 = 16.6 , P < 0.0001).
29. [4CB9X9XE-e30] no loose match (the pair of entities was not found)
   ours: [Occurred] Occurrence of feeding trial of Peromyscus maniculatus --causes--> [Absent] Absence of adult plant consumption of Elymus canadensis
   nearest gold (sim 0.41500000000000004): [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   sentence: We detected no consumption of plant parts of adult native species in our captive feeding trials.
30. [4CB9X9XE-e31] no loose match (the pair of entities was not found)
   ours: [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> [Increased] abundance of planted native seedlings
   nearest gold (sim 0.505): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] abundance of planted native seedlings
   sentence: The exclosed plots had twice the abundance of planted native seedlings ( F1,5 = 5.92 , P = 0.0196) and significantly higher richness of planted species ( F1.5 = 13.8 , P < 0.001) than areas lacking protection from small mammals (Figs 2 and S1).
31. [4CB9X9XE-e32] no loose match (the pair of entities was not found)
   ours: [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> [Increased] richness of planted native species
   nearest gold (sim 0.58375): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] species richness of planted prairie species
   sentence: The exclosed plots had twice the abundance of planted native seedlings ( F1,5 = 5.92 , P = 0.0196) and significantly higher richness of planted species ( F1.5 = 13.8 , P < 0.001) than areas lacking protection from small mammals (Figs 2 and S1).
32. [4CB9X9XE-e33] no loose match (the pair of entities was not found)
   ours: [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> [Increased] recruitment of Elymus canadensis
   nearest gold (sim 0.505): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   sentence: Most notable was E. canadensis (C3 grass), with 51 individuals observed in the exclosures, but none in open areas.
33. [4CB9X9XE-e34] no loose match (the pair of entities was not found)
   ours: [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> Recruitment of oldfield plants (NULL)
   nearest gold (sim 0.5275000000000001): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] recruitment of oldfield plants (NULL)
   sentence: There were no recruitment differences for oldfield plants inside vs. outside the exclosures.
34. [4CB9X9XE-e35] no loose match (the pair of entities was not found)
   ours: Mowing --causes--> [Increased] detection of native seed of Peromyscus maniculatus
   nearest gold (sim 0.685): [Occurred] Mowing (experimental defoliation) --contributes_to--> [Increased] seed detection by small mammals
   sentence: The richness of planted prairie species outside the cages was especially low in seeded plots that were experimentally defoliated with mowing (Fig. S1), suggesting that small mammals were more able to detect native seed in these
35. [4CB9X9XE-e36] no loose match (the pair of entities was not found)
   ours: Dietary preference of Peromyscus maniculatus --causes--> [Increased] consumption of Elymus canadensis
   nearest gold (sim 0.45999999999999996): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   sentence: We mostly observed the first outcome, with native consumers showing preferences for subsets of planted native prairie species despite their rarity regionally, and almost exclusively at times of peak seed output.
36. [4CB9X9XE-e37] no loose match (the pair of entities was not found)
   ours: Dietary preference of Peromyscus maniculatus --causes--> [Increased] consumption of Lespedeza capitata
   nearest gold (sim 0.41500000000000004): [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   sentence: We mostly observed the first outcome, with native consumers showing preferences for subsets of planted native prairie species despite their rarity regionally, and almost exclusively at times of peak seed output.
37. [4CB9X9XE-e38] no loose match (the pair of entities was not found)
   ours: [Increased] seed availability --causes--> [Increased] consumption of Elymus canadensis
   nearest gold (sim 0.5275000000000001): [Decreased] availability of native prairie seed --causes--> [Decreased] rodent consumption of native prairie seed
   sentence: The consumption of seeds of these plants were observed year-round in the monthly cafeteria trials, with same subset of species taken consistently and in the same order, suggesting that consumption levels in this system could be determined more by seed availability than by changes in consumer preference by season (i.e. seed consumption appears to end in late fall because of food limitation, rather than switching to different species).
38. [4CB9X9XE-e39] no loose match (the pair of entities was not found)
   ours: [Increased] seed availability --causes--> [Increased] consumption of Lespedeza capitata
   nearest gold (sim 0.5275000000000001): [Decreased] availability of native prairie seed --causes--> [Decreased] rodent consumption of native prairie seed
   sentence: The consumption of seeds of these plants were observed year-round in the monthly cafeteria trials, with same subset of species taken consistently and in the same order, suggesting that consumption levels in this system could be determined more by seed availability than by changes in consumer preference by season (i.e. seed consumption appears to end in late fall because of food limitation, rather than switching to different species).
39. [4CB9X9XE-e40] no loose match (the pair of entities was not found)
   ours: [Present] Presence of abundance of introduced species --contributes_to--> [Increased] population density of Peromyscus maniculatus
   nearest gold (sim 0.55): [Increased] Mustela erminea abundance --associated_with--> [Decreased] Peromyscus maniculatus population size
   sentence: However, with our observed deer mouse population densities at normal to high levels for southern Canada (Davidson & Morris 2001), the implication is that these introduced species provide sufficient resources to maintain rodent populations in this system.
40. [4CB9X9XE-e41] right entities, object attribute differs (similarity 0.00)
   ours: [Increased] population density of Peromyscus maniculatus --causes--> [Increased] granivory of Peromyscus maniculatus
   nearest gold (sim 0.0): [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   sentence: If true, the net effect is likely twofold: normal to high population levels of rodents being maintained, which in turn exerts intense granivore pressure thereby inhibiting recruitment by some native prairie plants.
41. [4CB9X9XE-e42] no loose match (the pair of entities was not found)
   ours: [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] recruitment of Elymus canadensis
   nearest gold (sim 0.41500000000000004): [Increased] rodent granivory on planted prairie species --causes--> [Decreased] recruitment of planted prairie species
   sentence: If true, the net effect is likely twofold: normal to high population levels of rodents being maintained, which in turn exerts intense granivore pressure thereby inhibiting recruitment by some native prairie plants.
42. [4CB9X9XE-e43] no loose match (the pair of entities was not found)
   ours: [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] recruitment of Lespedeza capitata
   nearest gold (sim 0.41500000000000004): [Increased] rodent granivory on planted prairie species --causes--> [Decreased] recruitment of planted prairie species
   sentence: If true, the net effect is likely twofold: normal to high population levels of rodents being maintained, which in turn exerts intense granivore pressure thereby inhibiting recruitment by some native prairie plants.
43. [4CB9X9XE-e44] no loose match (the pair of entities was not found)
   ours: [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] restoration success
   nearest gold (sim 0.64): [Increased] rodent granivory on planted prairie species --contributes_to--> [Decreased] restoration success of planted tallgrass prairie
   sentence: This targeted granviory may present a substantial challenge for the restoration success of planted high-diversity prairie, if subsets of species are preferentially consumed by native rodents once the prairie reaches canopy closure and rodent populations become established.
44. [4CB9X9XE-e45] no loose match (the pair of entities was not found)
   ours: [Increased] consumption of native seed of Peromyscus maniculatus --contributes_to--> [Increased] establishment of oldfield species
   nearest gold (sim 0.5275000000000001): [Increased] rodent granivory on planted prairie species --contributes_to--> [Increased] establishment of introduced oldfield species
   sentence: We observed high consumption levels of native seed by native consumers, suggesting the possible facilitation of introduced species initially – if natives plants were preferred, all things being equal, this would have provided fitness advantages for establishing invasive populations of incoming oldfield species introduced accidently or intentionally by humans (MacDougall, Gilbert & Levine 2009; Kalisz, Spigler & Horvitz 2014).
45. [4CB9X9XE-e46] no loose match (the pair of entities was not found)
   ours: Generalist feeding behavior of Peromyscus maniculatus --contributes_to--> [Increased] consumption of oldfield species
   nearest gold (sim 0.41500000000000004): [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   sentence: This result may derive partly by deer mice – the dominant rodent species in our system – being a generalist and sometimes opportunistic feeder (Davidson & Morris 2001).
46. [4CB9X9XE-e47] no loose match (the pair of entities was not found)
   ours: [Present] Presence of abundance of oldfield plants --contributes_to--> [Increased] diet composition of Peromyscus maniculatus
   nearest gold (sim 0.505): [Increased] Mustela erminea abundance --associated_with--> [Decreased] Peromyscus maniculatus population size
   sentence: It may also relate to oldfield plants, introduced but also including native species such as Canada goldenrod, now serving as the main standing carbohydrate reserve on the landscape, given the dominance of these plants across the region for at least the last century – it seems likely that there would have been strong pressure on rodents to utilize these flora.
47. [4CB9X9XE-e48] no loose match (the pair of entities was not found)
   ours: [Increased] density of Peromyscus maniculatus --contributes_to--> [Increased] diet breadth of oldfield species
   nearest gold (sim 0.45999999999999996): [Increased] rodent population density --correlated_with--> [Increased] number of oldfield species consumed by rodents
   sentence: For example, at peak rodent population density in July we observed the widest range of plant species in the rodent diet, including non-native and potentially invasive trees, grasses, and forbs, as well as the most rapid depletion of seed from the widest range of plants in the cafeteria trials – both suggest the possibility of density-related responses to food limitation, which can be fierce in deer mouse populations (Davidson & Morris 2001).
48. [4CB9X9XE-e49] right entities, but one side is a null result and the other a positive claim (null flags disagree)
   ours: [Increased] density of Peromyscus maniculatus --contributes_to--> [Increased] seed depletion of Peromyscus maniculatus
   nearest gold (sim 0.595): [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   sentence: For example, at peak rodent population density in July we observed the widest range of plant species in the rodent diet, including non-native and potentially invasive trees, grasses, and forbs, as well as the most rapid depletion of seed from the widest range of plants in the cafeteria trials – both suggest the possibility of density-related responses to food limitation, which can be fierce in deer mouse populations (Davidson & Morris 2001).
49. [4CB9X9XE-e50] no loose match (the pair of entities was not found)
   ours: [Decreased] density of Peromyscus maniculatus --associated_with--> [Increased] seed production of Elymus canadensis
   nearest gold (sim 0.45999999999999996): [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   sentence: Rodent densities subsequently dropped by 54% in the next month, despite peak seed production by preferred native species, and remained in decline for the rest of the year.
50. [4CB9X9XE-e51] no loose match (the pair of entities was not found)
   ours: [Increased] predation of Mustela erminea --contributes_to--> [Decreased] density of Peromyscus maniculatus
   nearest gold (sim 0.73): [Increased] Mustela erminea abundance --associated_with--> [Decreased] Peromyscus maniculatus population size
   sentence: There could also be a predatory influence of weasels, which were trapped in highest numbers in late summer.
51. [4CB9X9XE-e52] no loose match (the pair of entities was not found)
   ours: [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] persistence of Elymus canadensis
   nearest gold (sim 0.41500000000000004): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   sentence: However, this seems to be insufficient to shelter rarer prairie species from targeted granivory, which in turn may hamper their persistence.
52. [4CB9X9XE-e53] no loose match (the pair of entities was not found)
   ours: [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] persistence of Lespedeza capitata
   nearest gold (sim 0.41500000000000004): [Increased] rodent granivory on planted prairie species --causes--> [Decreased] persistence of rare prairie species
   sentence: However, this seems to be insufficient to shelter rarer prairie species from targeted granivory, which in turn may hamper their persistence.
53. [4CB9X9XE-e54] no loose match (the pair of entities was not found)
   ours: [Increased] density of Peromyscus maniculatus --causes--> Seed removal of Elymus canadensis (NULL)
   nearest gold (sim 0.4600000000000001): [Present] Presence of Peromyscus maniculatus in captive feeding trials --causes--> [Occurred] Herbivory on adult native prairie plants (NULL)
   sentence: There was no correlation between rodent densities by month and the removal of preferred seed from the feeding stations - removal was similarly high in summer during the population peak and when rodent numbers were low in winter (R2 = 0.210, P = 0.137).

## FIRST 10 FNs: gold node terms next to the closest predicted nodes

### FN 1 [4CB9X9XE-e01] [Increased] seed production of planted prairie species --associated_with--> [Increased] rodent consumption of planted prairie plants   (no_loose_match)
  gold SUBJECT: name='Increased seed production of planted prairie species' | taxa_ids=- taxa_text=- | entity_text=['production', 'seed'] | attr='seed output' | dir=UP
     closest predicted: name='Increased seed production of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['production', 'seed'] | attr='seed production' | dir=UP   [entity_agree=yes]
     closest predicted: name='Increased seed production of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['production', 'seed'] | attr='seed production' | dir=UP   [entity_agree=yes]
     closest predicted: name='Increased seed consumption of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['@consumption', 'seed'] | attr='seed consumption' | dir=UP   [entity_agree=no]
  gold OBJECT: name='Increased rodent consumption of planted prairie plants' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['@consumption', 'plant', 'prairie', 'rodent'] | attr='proportion of rodent diet' | dir=UP
     closest predicted: name='Native plant consumption' | taxa_ids=- taxa_text=- | entity_text=['@consumption', 'native', 'plant'] | attr=None | dir=NONE   [entity_agree=no]
     closest predicted: name='Increased abundance of planted native seedlings' | taxa_ids=- taxa_text=- | entity_text=['native', 'plant', 'seedl'] | attr='PATO:0000070' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased richness of planted native species' | taxa_ids=- taxa_text=- | entity_text=['native', 'plant', 'specy'] | attr='richness' | dir=UP   [entity_agree=no]

### FN 2 [4CB9X9XE-e02] [Decreased] availability of native prairie seed --causes--> [Decreased] rodent consumption of native prairie seed   (no_loose_match)
  gold SUBJECT: name='Decreased availability of native prairie seed' | taxa_ids=- taxa_text=- | entity_text=['availability', 'seed'] | attr=None | dir=DOWN
     closest predicted: name='Increased seed availability' | taxa_ids=- taxa_text=- | entity_text=['availability', 'seed'] | attr=None | dir=UP   [entity_agree=yes]
     closest predicted: name='Increased seed production of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['production', 'seed'] | attr='seed production' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased seed production of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['production', 'seed'] | attr='seed production' | dir=UP   [entity_agree=no]
  gold OBJECT: name='Decreased rodent consumption of native prairie seed' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['@consumption', 'plant', 'prairie', 'rodent'] | attr='consumption level' | dir=DOWN
     closest predicted: name='Decreased consumption of Andropogon gerardii' | taxa_ids=['NCBITaxon:79824'] taxa_text=['a.gerardi', 'a.gerardii'] | entity_text=['@consumption'] | attr='consumption' | dir=DOWN   [entity_agree=no]
     closest predicted: name='Decreased consumption of Peromyscus maniculatus' | taxa_ids=['NCBITaxon:10042'] taxa_text=['p.maniculatus'] | entity_text=['@consumption'] | attr='consumption' | dir=DOWN   [entity_agree=no]
     closest predicted: name='Native plant consumption' | taxa_ids=- taxa_text=- | entity_text=['@consumption', 'native', 'plant'] | attr=None | dir=NONE   [entity_agree=no]

### FN 3 [4CB9X9XE-e03] [Occurred] Rodent consumption of non-planted oldfield plants --contributes_to--> [Ongoing] persistence of rodent populations at normal to high levels   (no_loose_match)
  gold SUBJECT: name='Rodent consumption of non-planted oldfield plants' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['@consumption', 'oldfield', 'plant', 'rodent'] | attr=None | dir=OCCUR
     closest predicted: name='Presence of abundance of oldfield plants' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'plant'] | attr='PATO:0000070' | dir=OCCUR   [entity_agree=yes]
     closest predicted: name='Recruitment of oldfield plants' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'plant'] | attr='recruitment' | dir=NONE   [entity_agree=yes]
     closest predicted: name='Native plant consumption' | taxa_ids=- taxa_text=- | entity_text=['@consumption', 'native', 'plant'] | attr=None | dir=NONE   [entity_agree=no]
  gold OBJECT: name='Ongoing persistence of rodent populations at normal to high levels' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['level', 'normal', 'persistence', 'population', 'rodent'] | attr='population persistence' | dir=OCCUR
     closest predicted: name='Decreased persistence of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['persistence'] | attr='persistence' | dir=DOWN   [entity_agree=no]
     closest predicted: name='Decreased persistence of Lespedeza capitata' | taxa_ids=['NCBITaxon:571920'] taxa_text=['l.capitata'] | entity_text=['persistence'] | attr='persistence' | dir=DOWN   [entity_agree=no]
     closest predicted: name='Presence of abundance of oldfield species' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'specy'] | attr='PATO:0000070' | dir=OCCUR   [entity_agree=no]

### FN 4 [4CB9X9XE-e04] [Occurred] Rodent consumption of non-planted oldfield plants --prevents--> [Occurred] Rodent granivory on planted prairie species (NULL)   (no_loose_match)
  gold SUBJECT: name='Rodent consumption of non-planted oldfield plants' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['@consumption', 'oldfield', 'plant', 'rodent'] | attr=None | dir=OCCUR
     closest predicted: name='Presence of abundance of oldfield plants' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'plant'] | attr='PATO:0000070' | dir=OCCUR   [entity_agree=yes]
     closest predicted: name='Recruitment of oldfield plants' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'plant'] | attr='recruitment' | dir=NONE   [entity_agree=yes]
     closest predicted: name='Native plant consumption' | taxa_ids=- taxa_text=- | entity_text=['@consumption', 'native', 'plant'] | attr=None | dir=NONE   [entity_agree=no]
  gold OBJECT: name='Rodent granivory on planted prairie species' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['@consumption'] | attr=None | dir=NONE
     closest predicted: name='Seed removal of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['@consumption'] | attr='seed removal' | dir=NONE   [entity_agree=no]
     closest predicted: name='Increased granivory of Peromyscus maniculatus' | taxa_ids=['NCBITaxon:10042'] taxa_text=['p.maniculatus'] | entity_text=['@consumption'] | attr='granivory' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased consumption of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['@consumption'] | attr='consumption' | dir=UP   [entity_agree=no]

### FN 5 [4CB9X9XE-e05] [Increased] rodent granivory on planted prairie species --causes--> [Decreased] species richness of planted prairie species   (no_loose_match)
  gold SUBJECT: name='Increased rodent granivory on planted prairie species' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['@consumption'] | attr='intensity' | dir=UP
     closest predicted: name='Increased granivory of Peromyscus maniculatus' | taxa_ids=['NCBITaxon:10042'] taxa_text=['p.maniculatus'] | entity_text=['@consumption'] | attr='granivory' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased consumption of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['@consumption'] | attr='consumption' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased consumption of Lespedeza capitata' | taxa_ids=['NCBITaxon:571920'] taxa_text=['l.capitata'] | entity_text=['@consumption'] | attr='consumption' | dir=UP   [entity_agree=no]
  gold OBJECT: name='Decreased species richness of planted prairie species' | taxa_ids=- taxa_text=- | entity_text=['native', 'plant', 'prairie', 'specy'] | attr='species richness' | dir=DOWN
     closest predicted: name='Decreased species richness of planted native species' | taxa_ids=- taxa_text=- | entity_text=['native', 'plant', 'specy'] | attr='species richness' | dir=DOWN   [entity_agree=yes]
     closest predicted: name='Increased richness of planted native species' | taxa_ids=- taxa_text=- | entity_text=['native', 'plant', 'specy'] | attr='richness' | dir=UP   [entity_agree=yes]
     closest predicted: name='Native plant consumption' | taxa_ids=- taxa_text=- | entity_text=['@consumption', 'native', 'plant'] | attr=None | dir=NONE   [entity_agree=no]

### FN 6 [4CB9X9XE-e06] [Increased] rodent granivory on planted prairie species --contributes_to--> [Increased] establishment of introduced oldfield species   (no_loose_match)
  gold SUBJECT: name='Increased rodent granivory on planted prairie species' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['@consumption'] | attr='intensity' | dir=UP
     closest predicted: name='Increased granivory of Peromyscus maniculatus' | taxa_ids=['NCBITaxon:10042'] taxa_text=['p.maniculatus'] | entity_text=['@consumption'] | attr='granivory' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased consumption of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['@consumption'] | attr='consumption' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased consumption of Lespedeza capitata' | taxa_ids=['NCBITaxon:571920'] taxa_text=['l.capitata'] | entity_text=['@consumption'] | attr='consumption' | dir=UP   [entity_agree=no]
  gold OBJECT: name='Increased establishment of introduced oldfield species' | taxa_ids=- taxa_text=- | entity_text=['non', 'oldfield', 'plant', 'specy'] | attr='establishment' | dir=UP
     closest predicted: name='Increased establishment of oldfield species' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'specy'] | attr='establishment' | dir=UP   [entity_agree=yes]
     closest predicted: name='Recruitment of oldfield plants' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'plant'] | attr='recruitment' | dir=NONE   [entity_agree=yes]
     closest predicted: name='Increased consumption of oldfield species' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'specy'] | attr='consumption' | dir=UP   [entity_agree=yes]

### FN 7 [4CB9X9XE-e07] [Present] Presence of native rodents --causes--> [Decreased] restoration success of planted tallgrass prairie   (no_loose_match)
  gold SUBJECT: name='Presence of native rodents' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['native', 'presence', 'rodent'] | attr='presence' | dir=OCCUR
     closest predicted: name='Native plant consumption' | taxa_ids=- taxa_text=- | entity_text=['@consumption', 'native', 'plant'] | attr=None | dir=NONE   [entity_agree=no]
     closest predicted: name='Presence of abundance of oldfield species' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'specy'] | attr='PATO:0000070' | dir=OCCUR   [entity_agree=no]
     closest predicted: name='Occurrence of capture of Mustela erminea' | taxa_ids=['NCBITaxon:36723'] taxa_text=['m.erminea'] | entity_text=['capture', 'occurrence'] | attr='capture' | dir=OCCUR   [entity_agree=no]
  gold OBJECT: name='Decreased restoration success of planted tallgrass prairie' | taxa_ids=- taxa_text=- | entity_text=['restoration', 'success'] | attr=None | dir=DOWN
     closest predicted: name='Decreased restoration success' | taxa_ids=- taxa_text=- | entity_text=['restoration', 'success'] | attr=None | dir=DOWN   [entity_agree=yes]
     closest predicted: name='Decreased density of Peromyscus maniculatus' | taxa_ids=['NCBITaxon:10042'] taxa_text=['p.maniculatus'] | entity_text=['@density'] | attr='density' | dir=DOWN   [entity_agree=no]
     closest predicted: name='Decreased recruitment of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['@recruitment'] | attr='recruitment' | dir=DOWN   [entity_agree=no]

### FN 8 [4CB9X9XE-e08] [Increased] rodent granivory on planted prairie species --causes--> [Decreased] recruitment of planted prairie species   (no_loose_match)
  gold SUBJECT: name='Increased rodent granivory on planted prairie species' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['@consumption'] | attr='intensity' | dir=UP
     closest predicted: name='Increased granivory of Peromyscus maniculatus' | taxa_ids=['NCBITaxon:10042'] taxa_text=['p.maniculatus'] | entity_text=['@consumption'] | attr='granivory' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased consumption of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['@consumption'] | attr='consumption' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased consumption of Lespedeza capitata' | taxa_ids=['NCBITaxon:571920'] taxa_text=['l.capitata'] | entity_text=['@consumption'] | attr='consumption' | dir=UP   [entity_agree=no]
  gold OBJECT: name='Decreased recruitment of planted prairie species' | taxa_ids=- taxa_text=- | entity_text=['native', 'plant', 'prairie', 'specy'] | attr='recruitment' | dir=DOWN
     closest predicted: name='Decreased species richness of planted native species' | taxa_ids=- taxa_text=- | entity_text=['native', 'plant', 'specy'] | attr='species richness' | dir=DOWN   [entity_agree=yes]
     closest predicted: name='Increased richness of planted native species' | taxa_ids=- taxa_text=- | entity_text=['native', 'plant', 'specy'] | attr='richness' | dir=UP   [entity_agree=yes]
     closest predicted: name='Decreased recruitment of Elymus canadensis' | taxa_ids=['NCBITaxon:29675'] taxa_text=['e.canadensis'] | entity_text=['@recruitment'] | attr='recruitment' | dir=DOWN   [entity_agree=no]

### FN 9 [4CB9X9XE-e09] [Present] Late-summer period (August-September) --associated_with--> [Increased] rodent consumption of planted prairie plants   (no_loose_match)
  gold SUBJECT: name='Late-summer period (August-September)' | taxa_ids=- taxa_text=- | entity_text=['time', 'year'] | attr='season' | dir=OCCUR
     closest predicted: name='Presence of abundance of oldfield species' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'specy'] | attr='PATO:0000070' | dir=OCCUR   [entity_agree=no]
     closest predicted: name='Occurrence of capture of Mustela erminea' | taxa_ids=['NCBITaxon:36723'] taxa_text=['m.erminea'] | entity_text=['capture', 'occurrence'] | attr='capture' | dir=OCCUR   [entity_agree=no]
     closest predicted: name='Occurrence of feeding trial of Peromyscus maniculatus' | taxa_ids=['NCBITaxon:10042'] taxa_text=['p.maniculatus'] | entity_text=['feed', 'occurrence', 'trial'] | attr='feeding trial' | dir=OCCUR   [entity_agree=no]
  gold OBJECT: name='Increased rodent consumption of planted prairie plants' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['@consumption', 'plant', 'prairie', 'rodent'] | attr='proportion of rodent diet' | dir=UP
     closest predicted: name='Native plant consumption' | taxa_ids=- taxa_text=- | entity_text=['@consumption', 'native', 'plant'] | attr=None | dir=NONE   [entity_agree=no]
     closest predicted: name='Increased abundance of planted native seedlings' | taxa_ids=- taxa_text=- | entity_text=['native', 'plant', 'seedl'] | attr='PATO:0000070' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased richness of planted native species' | taxa_ids=- taxa_text=- | entity_text=['native', 'plant', 'specy'] | attr='richness' | dir=UP   [entity_agree=no]

### FN 10 [4CB9X9XE-e11] [Increased] rodent population density --correlated_with--> [Increased] number of oldfield species consumed by rodents   (no_loose_match)
  gold SUBJECT: name='Increased rodent population density' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['@density', 'population', 'rodent'] | attr='population density' | dir=UP
     closest predicted: name='Increased population density of Peromyscus maniculatus' | taxa_ids=['NCBITaxon:10042'] taxa_text=['p.maniculatus'] | entity_text=['@density', 'population'] | attr='population density' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased population density of Zapus hudsonius' | taxa_ids=['NCBITaxon:160400'] taxa_text=['z.hudsonius'] | entity_text=['@density', 'population'] | attr='population density' | dir=UP   [entity_agree=no]
     closest predicted: name='Increased density of Peromyscus maniculatus' | taxa_ids=['NCBITaxon:10042'] taxa_text=['p.maniculatus'] | entity_text=['@density'] | attr='density' | dir=UP   [entity_agree=no]
  gold OBJECT: name='Increased number of oldfield species consumed by rodents' | taxa_ids=['NCBITaxon:9989'] taxa_text=- | entity_text=['non', 'oldfield', 'plant', 'specy'] | attr='number of species consumed by rodents' | dir=UP
     closest predicted: name='Increased consumption of oldfield species' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'specy'] | attr='consumption' | dir=UP   [entity_agree=yes]
     closest predicted: name='Increased establishment of oldfield species' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'specy'] | attr='establishment' | dir=UP   [entity_agree=yes]
     closest predicted: name='Increased diet breadth of oldfield species' | taxa_ids=- taxa_text=- | entity_text=['oldfield', 'specy'] | attr='diet breadth' | dir=UP   [entity_agree=yes]
