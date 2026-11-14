# False positives with reason 'no loose match', both papers (dev_baseline)

## 4CB9X9XE (corpus 4CB9X9XE)
- predicted edges 54, false positives 53, of which no loose match 51
- no-loose-match FPs by section of the cited sentence: {'abs': 11, 'res': 24, 'dis': 16}
- all predicted edges by section: {'abs': 11, 'res': 25, 'dis': 18}
- sentences given to the model by section: {'abs': 18, 'res': 28, 'dis': 22}

## murphy2005 (corpus YKQQZV93)
- predicted edges 77, false positives 38, of which no loose match 13
- no-loose-match FPs by section of the cited sentence: {'abs': 4, 'res': 2, 'dis': 7}
- all predicted edges by section: {'abs': 15, 'res': 47, 'dis': 15}
- sentences given to the model by section: {'abs': 8, 'res': 29, 'cap': 8, 'dis': 25}

## Both papers together: 64 no-loose-match FPs by section: {'abs': 15, 'res': 26, 'dis': 23}

## 15 random examples (seed 7)

1. [4CB9X9XE 4CB9X9XE-e44] section=dis sentence n=56
   ours: [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] restoration success
   nearest gold (sim 0.64): [Increased] rodent granivory on planted prairie species --contributes_to--> [Decreased] restoration success of planted tallgrass prairie
   text: This targeted granviory may present a substantial challenge for the restoration success of planted high-diversity prairie, if subsets of species are preferentially consumed by native rodents once the prairie reaches canopy closure and rodent populations become established.
2. [murphy2005 YKQQZV93-e62] section=dis sentence n=69
   ours: [Increased] abundance of Sanguinaria canadensis --enables--> Forest edge ecosystem redevelopment
   nearest gold (sim 0.559): [Present] reestablishment of Sanguinaria canadensis --contributes_to--> [Occurred] reassembly of forest ecosystems
   text: If so, a forest edge ecosystem may redevelop one that is less hostile to native species, including the shrubs and trees that will give it a more impermeable structure.
3. [4CB9X9XE 4CB9X9XE-e10] section=abs sentence n=16
   ours: [Increased] granivory of Peromyscus maniculatus --causes--> [Decreased] recruitment of Elymus canadensis
   nearest gold (sim 0.41500000000000004): [Increased] rodent granivory on planted prairie species --causes--> [Decreased] recruitment of planted prairie species
   text: These findings suggest that rodents may reduce the restoration success of tallgrass prairie in our region, with some planted species likely to suffer future recruitment difficulties due to granivory.
4. [4CB9X9XE 4CB9X9XE-e27] section=res sentence n=39
   ours: [Occurred] Occurrence of feeding trial of Peromyscus maniculatus --causes--> [Increased] consumption of Helianthus divaricatus
   nearest gold (sim 0.41500000000000004): [Decreased] Depletion of preferred seed supply --precedes--> [Occurred] Seedling herbivory by deer mice
   text: The captive feeding trials demonstrated the identical order of seed consumption as observed in the field, with preferences for the same four species (Fig. 3,  $F_{3.7} = 117$ , P < 0.0001, Tukey's HSD).
5. [murphy2005 YKQQZV93-e75] section=dis sentence n=56
   ours: [Occurred] Occurrence of planting of Sanguinaria canadensis --causes--> Native species regeneration (NULL)
   nearest gold (sim 0.604): [Introduced] Sanguinaria canadensis density treatment --causes--> [Increased] number of individuals of other native species (NULL)
   text: In my study, there is no evidence yet of regeneration of other native species from the existing propagules.
6. [4CB9X9XE 4CB9X9XE-e4] section=abs sentence n=11
   ours: Food limitation --causes--> [Increased] consumption of Lespedeza capitata
   nearest gold (sim 0.3025): [Increased] rodent population density --associated_with--> [Increased] removal of Andropogon gerardii seed
   text: Cafeteria trials suggested diet seasonality to be explained by food limitation – native prairie seeds were consumed year-round when made available.
7. [4CB9X9XE 4CB9X9XE-e5] section=abs sentence n=12
   ours: [Present] Presence of abundance of oldfield species --contributes_to--> [Increased] population density of Peromyscus maniculatus
   nearest gold (sim 0.55): [Increased] Mustela erminea abundance --associated_with--> [Decreased] Peromyscus maniculatus population size
   text: Non-targeted oldfield species thus appeared to be of sufficient quality to support rodent populations (peaking at 23 individuals ha<sup>1</sup> in summer), but without rescuing rarer prairie species from targeted granivory and resulting in reduced prairie diversity outside of experimental exclosures.
8. [murphy2005 YKQQZV93-e2] section=abs sentence n=1
   ours: [Increased] forest fragmentation --causes--> [Increased] microenvironmental change
   nearest gold (sim 0.28): [Increased] Sanguinaria canadensis initial ramet density --causes--> [Increased] Alliaria petiolata seedling mortality before maturity
   text: One of the proximate results of forest fragmentation, and a cause of continued microenvironmental change and exacerbation of ecological problems, is increased invasions by weedy plant species.
9. [4CB9X9XE 4CB9X9XE-e36] section=dis sentence n=50
   ours: Dietary preference of Peromyscus maniculatus --causes--> [Increased] consumption of Elymus canadensis
   nearest gold (sim 0.45999999999999996): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   text: We mostly observed the first outcome, with native consumers showing preferences for subsets of planted native prairie species despite their rarity regionally, and almost exclusively at times of peak seed output.
10. [4CB9X9XE 4CB9X9XE-e7] section=abs sentence n=12
   ours: [Present] Presence of abundance of oldfield species --disrupts--> [Decreased] recruitment of Elymus canadensis
   nearest gold (sim 0.5275): [Present] Presence of introduced oldfield plant species --contributes_to--> [Decreased] recruitment of planted prairie species
   text: Non-targeted oldfield species thus appeared to be of sufficient quality to support rodent populations (peaking at 23 individuals ha<sup>1</sup> in summer), but without rescuing rarer prairie species from targeted granivory and resulting in reduced prairie diversity outside of experimental exclosures.
11. [4CB9X9XE 4CB9X9XE-e25] section=res sentence n=39
   ours: [Occurred] Occurrence of feeding trial of Peromyscus maniculatus --causes--> [Increased] consumption of Elymus canadensis
   nearest gold (sim 0.45999999999999996): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings
   text: The captive feeding trials demonstrated the identical order of seed consumption as observed in the field, with preferences for the same four species (Fig. 3,  $F_{3.7} = 117$ , P < 0.0001, Tukey's HSD).
12. [4CB9X9XE 4CB9X9XE-e39] section=dis sentence n=51
   ours: [Increased] seed availability --causes--> [Increased] consumption of Lespedeza capitata
   nearest gold (sim 0.5275000000000001): [Decreased] availability of native prairie seed --causes--> [Decreased] rodent consumption of native prairie seed
   text: The consumption of seeds of these plants were observed year-round in the monthly cafeteria trials, with same subset of species taken consistently and in the same order, suggesting that consumption levels in this system could be determined more by seed availability than by changes in consumer preference by season (i.e. seed consumption appears to end in late fall because of food limitation, rather than switching to different species).
13. [murphy2005 YKQQZV93-e59] section=dis sentence n=58
   ours: [Increased] abundance of Alliaria petiolata --prevents--> Native species reestablishment
   nearest gold (sim 0.41500000000000004): [Occurred] leafing phenology of year 2 Alliaria petiolata --associated_with--> [Occurred] leafing phenology of Sanguinaria canadensis ramets
   text: The absence of any significant reestablishment of other natives may be explained by their inability to compete with the still high densities of A. petiolata, the generally higher densities of S. canadensis, a lack of seed bank or immigration sources, and an ecosystem that cannot support their natural regeneration, especially in terms of the mycorrhizal and decomposition communities (Baar & Kuyper 1998; Emmerling 1998; Ehrlen & Eriksson 2000; Butaye et al. 2002; Tyler et al. 2002).
14. [4CB9X9XE 4CB9X9XE-e34] section=res sentence n=45
   ours: [Introduced] Introduction of exclusion of Peromyscus maniculatus --causes--> Recruitment of oldfield plants (NULL)
   nearest gold (sim 0.5275000000000001): [Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] recruitment of oldfield plants (NULL)
   text: There were no recruitment differences for oldfield plants inside vs. outside the exclosures.
15. [4CB9X9XE 4CB9X9XE-e15] section=res sentence n=29
   ours: [Increased] density of Peromyscus maniculatus --correlated_with--> [Increased] consumption of oldfield species
   nearest gold (sim 0.45999999999999996): [Increased] rodent population density --correlated_with--> [Increased] number of oldfield species consumed by rodents
   text: Rodent density per month and numbers of oldfield species consumed per month were positively correlated ( $R^2 = 0.166$ , P = 0.041), while no relationship was detectable between rodent density and native plant consumption  $(R^2 = 0.0786,$ P = 0.43).