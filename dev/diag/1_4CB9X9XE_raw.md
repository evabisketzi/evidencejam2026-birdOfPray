# 4CB9X9XE, baseline: raw model lines, legend, context

NOTE: the dev_baseline run used --no-cache, so its raw lines were not stored. These lines are the cached FULL baseline run
of the same paper with the same prompt (system.txt, temperature 0). It is a different sample from the dev run
(here 5828 prompt / 1274 completion tokens; dev: 5709 / 1144), so line numbers are not the dev FN/FP ids.

## SPECIES legend given to the model
SPECIES: T1=Peromyscus maniculatus (species); T2=Elymus canadensis (E. canadensis); T3=Lespedeza capitata (L. capitata, forb); T4=Mustela erminea (M. erminea); T5=Rudbeckia hirta (R. hirta, forb, trial); T6=Zapus hudsonius (Z. hudsonius); T7=Andropogon gerardii (A. gerardii); T8=Bromus kalmii (B. kalmii); T9=Helianthus divaricatus (H. divaricatus, sunflower); T10=Solidago canadensis (native oldfield species); T11=Sorghastrum nutans

## CONTEXT line given to the model
CONTEXT: Using molecular techniques combined with field experiments including cafeteria and captive feeding trials we test for seasonal rodent dietary preferences, specifically examining whether rodents favour planted native prairie species, non-targeted exotic and native oldfield species, or both, and how these preferences affect restoration success. We then explore the implications for restoring native plant diversity, in terms of impacts on non-targeted flora (i.e. the potential for rodent-based biotic resistance or acceptance) and for the planted native prairie plants that are currently regionally rare (e.g. the potential for increased rarity via rodent consumption, or potential protection via frequency-based rarity advantages). We focused on two groups of plants – planted native prairie species now rare and considered at-risk regionally, and non-planted oldfield species that are widely distributed regionally including the two native species considered problematic to farmed and restored areas (e.g. C. canadensis has evolved resistance to glyphosate). Seed for the planted species in the 18 ha study area was obtained within the region (the Grand River watershed of southwestern Ontario). Rodent live-trapping occurred from December 2011 to December 2012 covering ~ 1 ha of the prairie study area. Fifty Sherman Live Traps (5 × 7 × 27 cm) were spaced along five 150 m parallel transects that ran from the surrounding invaded area into the planted prairie – 5 traps were in the unplanted area (each 5 m from the planted prairie boundary) and 45 in the prairie. The traps were removed after each sampling period to avoid habituation. The DNA data indicated that rodents were primarily consuming planted prairie species in 2 months – August and September; diet in the remaining 10 months consisted of mostly non-targeted oldfield species occurring in the prairie and in surrounding areas (see Results below).

## Raw model output
F|10|T2/seed production/+/proc|a|T2/consumption/+;T3/consumption/+|A|obs|season=late_spring
F|11|food limitation/proc|c|T2/consumption/+;T3/consumption/+|U|exp|season=growing_season
F|12|non-targeted oldfield species/abundance/+/com|ct|T1/population density/+;T6/population density/+|U|obs|season=summer
F|12|non-targeted oldfield species/abundance/+/com|p|T2/recruitment/-;T3/recruitment/-|U|obs
F|16|T1/granivory/+;T6/granivory/+|c|T2/restoration success/-;T3/restoration success/-|U|obs
F|19|season/late_spring|c|T2/consumption/+;T3/consumption/+|D|obs
F|26|T4/capture/+/tax|cw|T1/population size/-|A|obs|season=late_spring
F|29|T1/density/+;T6/density/+|cw|oldfield species/consumption/+|A|obs
N|29|T1/density/+;T6/density/+|c|native plant consumption|obs
F|31|season/winter|c|T2/seed consumption/-;T3/seed consumption/-|D|obs
F|32|T1/seed caching/abs|c|T2/seed consumption/-;T3/seed consumption/-|D|obs
F|35|T1/feeding preference/+|c|T2/consumption/+;T3/consumption/+;T9/consumption/+;T7/consumption/-|D|exp
F|36|T1/density/+|c|T7/consumption/+|D|exp|season=summer
F|37|T2/seed production/+|c|T1/seed removal/-|D|exp|season=late_spring
F|39|T1/feeding preference/+|c|T2/consumption/+;T3/consumption/+;T9/consumption/+;T7/consumption/-|D|exp
F|41|T2/seed consumption/+|pr|T2/seedling herbivory/+;T3/seedling herbivory/+|D|exp
N|42|T1/herbivory/+|c|T2/adult plant parts consumption|exp
F|43|small-mammal exclosure/intro/mgmt|c|T2/seedling abundance/+;T3/seedling abundance/+;planted native species/richness/+|D|exp
F|44|small-mammal exclosure/intro/mgmt|c|T2/number of individuals/+|D|exp
N|45|small-mammal exclosure/intro/mgmt|c|oldfield plants/recruitment|exp
F|46|mowing/intro/mgmt|c|T1/detection of native seed/+|U|exp
F|50|T1/dietary preference/+|c|T2/consumption/+;T3/consumption/+|D|obs
F|51|seed availability/+|c|T2/consumption/+;T3/consumption/+|U|obs
F|54|introduced species/abundance/+|ct|T1/population density/+;T6/population density/+|U|obs
F|55|T1/population density/+;T6/population density/+|c|T2/recruitment/-;T3/recruitment/-|U|obs
F|56|T1/granivory/+;T6/granivory/+|c|T2/restoration success/-;T3/restoration success/-|U|obs
F|57|T1/consumption of native seed/+|ct|oldfield species/establishment/+|U|obs
F|59|T1/generalist feeding behavior|ct|oldfield species/consumption/+|U|obs
F|60|oldfield plants/abundance/+|ct|T1/diet composition/+|U|obs
F|62|T1/density/+|ct|oldfield species/diet breadth/+;T1/seed depletion rate/+|U|obs|season=summer
F|63|T1/density/-|c|T2/seed consumption/-|D|obs|season=late_spring
F|64|T4/predation/+|ct|T1/density/-|U|obs|season=late_spring
F|68|T1/granivory/+|c|T2/persistence/-;T3/persistence/-|U|obs
F|16|T1/granivory/+;T6/granivory/+|c|T2/restoration success/-;T3/restoration success/-|U|obs
F|29|T1/density/+;T6/density/+|cw|oldfield species/consumption/+|A|obs
N|29|T1/density/+;T6/density/+|c|native plant consumption|obs
F|55|T1/population density/+;T6/population density/+|c|T2/recruitment/-;T3/recruitment/-|U|obs
F|56|T1/granivory/+;T6/granivory/+|c|T2/restoration success/-;T3/restoration success/-|U|obs

## Numbered sentences given (n, section, text)
[1] (abs) - 1.
[2] (abs) Clarifying what species are being consumed at what times can improve our understanding of how anthropogenic change affects food web dynamics, with implications for community assembly including restoration.
[3] (abs) This includes human-based changes to plant communities via species introductions, which can interact with consumer feeding preferences to indirectly alter assembly outcomes including reduced restoration success if planted species are preferentially targeted.
[4] (abs) - 2.
[5] (abs) We used DNA barcoding of plant material in rodent scat, combined with field-based feeding trials, rodent trapping, and rodent exclosures to test for dietary preferences and assembly impacts of native rodents on a restored and regionally rare tallgrass prairie of central North America.
[6] (abs) We examined whether native rodents preferred non-targeted and mostly non-native oldfield plants that are more locally abundant, thus protecting the rarer native planted species from consumption, or if rodents preferred native plants regardless of abundance.
[7] (abs) - 3.
[8] (abs) Our results supported the latter outcome.
[9] (abs) Barcoding revealed that native rodents consumed mostly non-planted oldfield species for 10 months of the year (92% of the diet).
[10] (abs) The exceptions were August–September, when planted prairie species accounted for 87% of plants consumed and coincided with their peak seed production.
[11] (abs) Cafeteria trials suggested diet seasonality to be explained by food limitation – native prairie seeds were consumed year-round when made available.
[12] (abs) Non-targeted oldfield species thus appeared to be of sufficient quality to support rodent populations (peaking at 23 individuals ha1 in summer), but without rescuing rarer prairie species from targeted granivory and resulting in reduced prairie diversity outside of experimental exclosures.
[13] (abs) - 4.
[14] (abs) Synthesis and applications.
[15] (abs) Our work illustrates how anthropogenic-based changes to producer communities may affect feeding pathways in grassland food webs, potentially facilitating establishment by non-target species via indirect consumer effects that can be difficult to detect.
[16] (abs) These findings suggest that rodents may reduce the restoration success of tallgrass prairie in our region, with some planted species likely to suffer future recruitment difficulties due to granivory.
[17] (abs) Managers may need to consider multiple trophic levels with restoration, not just the commonly planted producer communities but also the consumers and predators associated with them.
[18] (abs) Key-words: diet seasonality, DNA barcoding, granivory, grassland food webs, native rodents, Peromyscus maniculatus, plant invasion, Sorghastrum nutans, tallgrass prairie, Zapus hudsonius
[19] (res) We detected pronounced seasonal diet trends with the monthly DNA sampling, with non-targeted oldfield species constituting most of the diet annually except in late summer when rodents preferentially consumed subsets of native prairie plants presumably as seed [sig].
[20] (res) In total, oldfield plants made up 92% of species in the rodent diet all months except August and September, with planted prairie species accounting for 87% of the rodent diet during that period.
[21] (res) There were 38 species detected within the 60 scat samples including bryophytes (Table S3), with vascular flora representing 26% of all species known to occur in the entire 50 ha study area (i.e. planted and surrounding area – Table S1).
[22] (res) There were 228 rodent captures, with 87 individual animals ear-tagged over the 12 month sampling period.
[23] (res) The number of individual captures per ha varied widely by season, as is typical for grassland rodents, with peak densities in mid-summer (July) and prior to the peak in consumption of native plants (August-September) (Fig. 3, Table 1).
[24] (res) Peromyscus maniculatus, captured every month including during winter, and Z. hudsonius, captured from May through September, were the most abundant species.
[25] (res) Recaptured animals averaged 2.91 individuals per month (SE = 0.54), and this did not vary seasonally (Wilcoxon test, P = 0.443).
[26] (res) Nine M. erminea were captured in the latter months of the year (December 2011 and August-November 2012), and were correlated with a sixfold reduction of deer mouse population size during August and September 2012 (Table 1).
[27] (res) Six M. erminea captures occurred in traps that also contained a mutilated mouse carcass.
[28] (res) There were varying relationships between the density of the rodent community by month and the rodent diet as revealed by the DNA analysis (Fig. 4).
[29] (res) Rodent density per month and numbers of oldfield species consumed per month were positively correlated [sig], while no relationship was detectable between rodent density and native plant consumption [ns].
[30] (res) The latter result was explained by native plant consumption at both high and low rodent densities (July and November respectively).
[31] (res) No planted native prairie species were observed in the scat samples in most months of the winter and spring, suggesting that seeds released during autumn were completely consumed, harder to detect by rodents at those times, or that the rodents had switched their preferences to non-native species.
[32] (res) This result indicates that rodents are not seed caching native prairie plants.
[33] (res) Seed removals from the cafeteria trials occurred in every month, with no seasonal variation in species preference based on order of removal from the feeding stations (i.e. the same subset of species were always consumed first areas – species richness was reduced on average 46 9 compared to the same treatment in the cages (F1,47 = 723, P = 00104 Tukey's HSD).
[34] (res) - Fig. 1).
[35] (res) In all months, rodents targeted the same four species: a tree (A. saccarhum), two large-seeded native forbs (H. divaricatus and L. capitata) and a native C3 grass (E. canadensis).
[36] (res) Andropogon gerardii, which was ignored most months, was consumed during June and July when rodent densities were highest, while the remaining two species (B. kalmii and R. hirta) were almost never taken (F11,156 = 2.039, P = 0.0281 Tukey's HSD).
[37] (res) There were variations among months in the amount of seed taken - removals from the cafeteria stations dropped significantly in late summer [sig] Tukey's HSD), which corresponded with the peak in seed production in the field, when the planted species were most prevalent in DNA scat, but also when rodent captures declined (Fig. 4).
[38] (res) There was no correlation between rodent densities by month and the removal of preferred seed from the feeding stations - removal was similarly high in summer during the population peak and when rodent numbers were low in winter [ns].
[39] (res) The captive feeding trials demonstrated the identical order of seed consumption as observed in the field, with preferences for the same four species (Fig. 3, F3.7 = 117, P < 0.0001, Tukey's HSD).
[40] (res) Three of the seven species had their seeds entirely consumed after 5 days (Fig. 4).
[41] (res) Seedling herbivory was only observed after all preferred seeds were taken, and only for two Asteraceae forb species out of the seven planted species [sig].
[42] (res) We detected no consumption of plant parts of adult native species in our captive feeding trials.
[43] (res) The exclosed plots had twice the abundance of planted native seedlings [sig] and significantly higher richness of planted species ( F1.5 = 13.8, P < 0.001) than areas lacking protection from small mammals (Figs 2 and S1).
[44] (res) Most notable was E. canadensis (C3 grass), with 51 individuals observed in the exclosures, but none in open areas.
[45] (res) There were no recruitment differences for oldfield plants inside vs. outside the exclosures.
[46] (res) The richness of planted prairie species outside the cages was especially low in seeded plots that were experimentally defoliated with mowing (Fig. S1), suggesting that small mammals were more able to detect native seed in these
[47] (dis) We tested for seasonal dietary preferences of native consumers in a restored and anthropogenically transformed plant community, where formerly widespread native plants are now isolated with a regional matrix of introduced and native oldfield species including some considered invasive to North American native grassland.
[48] (dis) We specifically examined the relative preferences of native rodent consumers for prairie vs. non-targeted and regionally widespread oldfield plants under open conditions (i.e. free-ranging animals), whether these preferences changed seasonally, the potential impacts on the diversity of one or both plant communities, and how this affected restoration success several years after planting.
[49] (dis) Past work on anthropogenic-based changes to resource–consumer interactions (i.e. combinations of native and non-native producers and consumers, which is increasingly common globally) has suggested a range of possible outcomes, which can be hard to test given the difficulty in tracking consumption patterns of free ranging individuals and whether these patterns change by season.
[50] (dis) We mostly observed the first outcome, with native consumers showing preferences for subsets of planted native prairie species despite their rarity regionally, and almost exclusively at times of peak seed output.
[51] (dis) The consumption of seeds of these plants were observed year-round in the monthly cafeteria trials, with same subset of species taken consistently and in the same order, suggesting that consumption levels in this system could be determined more by seed availability than by changes in consumer preference by season (i.e. seed consumption appears to end in late fall because of food limitation, rather than switching to different species).
[52] (dis) At other times of the year, the rodent community diet consisted of a wide array of oldfield plants, some that are invasive to restored prairie and occur widely within the region, with no indication, based on the DNA evidence, of herbivory on adult native prairie plants or the caching of their seed.
[53] (dis) We cannot comment on the diet of the rodent community prior to the arrival of exotic plants in the 19th century, or how the present-day diet would change if native plant populations were more widespread.
[54] (dis) However, with our observed deer mouse population densities at normal to high levels for southern Canada, the implication is that these introduced species provide sufficient resources to maintain rodent populations in this system.
[55] (dis) If true, the net effect is likely twofold: normal to high population levels of rodents being maintained, which in turn exerts intense granivore pressure thereby inhibiting recruitment by some native prairie plants.
[56] (dis) This targeted granviory may present a substantial challenge for the restoration success of planted high-diversity prairie, if subsets of species are preferentially consumed by native rodents once the prairie reaches canopy closure and rodent populations become established.
[57] (dis) We observed high consumption levels of native seed by native consumers, suggesting the possible facilitation of introduced species initially – if natives plants were preferred, all things being equal, this would have provided fitness advantages for establishing invasive populations of incoming oldfield species introduced accidently or intentionally by humans.
[58] (dis) However, we also see that these regionally prevalent oldfield species now constitute the bulk of the rodent diet in most months.
[59] (dis) This result may derive partly by deer mice – the dominant rodent species in our system – being a generalist and sometimes opportunistic feeder.
[60] (dis) It may also relate to oldfield plants, introduced but also including native species such as Canada goldenrod, now serving as the main standing carbohydrate reserve on the landscape, given the dominance of these plants across the region for at least the last century – it seems likely that there would have been strong pressure on rodents to utilize these flora.
[61] (dis) This reliance on mostly non-native oldfield plants plays an unclear role in the current regulation of these plant populations, in our restored prairie and more generally within our study region.
[62] (dis) For example, at peak rodent population density in July we observed the widest range of plant species in the rodent diet, including non-native and potentially invasive trees, grasses, and forbs, as well as the most rapid depletion of seed from the widest range of plants in the cafeteria trials – both suggest the possibility of density-related responses to food limitation, which can be fierce in deer mouse populations.
[63] (dis) Rodent densities subsequently dropped by 54% in the next month, despite peak seed production by preferred native species, and remained in decline for the rest of the year.
[64] (dis) There could also be a predatory influence of weasels, which were trapped in highest numbers in late summer.
[65] (dis) This accidental observation of weasel predation does raise an important consideration for grassland restoration – the emphasis tends to be on plants species with an assumed 'build it and they will come' model for associated insects, herbivores and predators.
[66] (dis) As our work suggests, not all of these groups may re-appear in similar abundance or at similar times, with the potential for strong and unanticipated effects such as selective rodent granivory.
[67] (dis) Our most striking finding, deriving largely from the DNA data, was the strong seasonal switching of plant consumption between planted vs. oldfield plants, and its implications for how consumer–producer interactions shape restoration outcomes in our system.
[68] (dis) However, this seems to be insufficient to shelter rarer prairie species from targeted granivory, which in turn may hamper their persistence.
