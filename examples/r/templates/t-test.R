d <- read.csv("your_data.csv")
stopifnot(all(c("group","outcome") %in% names(d)))
d$group <- factor(d$group)
stopifnot(nlevels(d$group)==2)
boxplot(outcome ~ group,data=d)
t.test(outcome ~ group,data=d) # Welch test by default
