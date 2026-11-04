source("_common.R")
d <- read.csv("cross_sectional_survey.csv"); d <- d[complete.cases(d[c("age","social_support","stress","well_being")]),]
first <- lm(well_being~age,d); second <- lm(well_being~age+social_support,d); third <- lm(well_being~age+social_support+stress,d)
comparison <- anova(first,second,third); print(comparison); print(summary(third))
finish(c(delta_r_squared=summary(third)$r.squared-summary(second)$r.squared,F=comparison$F[3],df1=comparison$Df[3],df2=df.residual(third),p=comparison$"Pr(>F)"[3]),list(comparison=data.frame(model=rownames(comparison),comparison)))

