d <- read.csv("your_data.csv")
stopifnot(nlevels(factor(d$group))==2)
parts <- split(d$outcome,d$group); a <- na.omit(parts[[1]]); b <- na.omit(parts[[2]])
pooled_sd <- sqrt(((length(a)-1)*var(a)+(length(b)-1)*var(b))/(length(a)+length(b)-2))
cohens_d <- (mean(a)-mean(b))/pooled_sd; cohens_d
