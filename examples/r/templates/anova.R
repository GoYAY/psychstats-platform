d <- read.csv("your_data.csv")
stopifnot(all(c("group","outcome") %in% names(d)))
d$group <- factor(d$group)
fit <- aov(outcome ~ group,data=d)
plot(fit); summary(fit)
TukeyHSD(fit) # Use only when the design and assumptions support this comparison.
