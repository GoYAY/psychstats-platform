d <- read.csv("your_data.csv")
x <- na.omit(d$score)
se_mean <- sd(x)/sqrt(length(x)); se_mean
# The formula assumes independent observations; clustered data need another method.
