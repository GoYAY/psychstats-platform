d <- read.csv("your_data.csv")
stopifnot(nlevels(factor(d$group))==2)
t.test(outcome ~ group,data=d) # Interpret the p-value with effect size and interval.
