source("examples/r/analyses/_common.R")
d <- read_data("nested_classrooms")
fit <- nlme::lme(achievement ~ motivation + teacher_support, random=~1|class_id, data=d, method="REML")
emit(c(motivation_beta=unname(nlme::fixef(fit)["motivation"]), teacher_beta=unname(nlme::fixef(fit)["teacher_support"]), converged=1))
