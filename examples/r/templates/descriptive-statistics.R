d <- read.csv("your_data.csv")
stopifnot(is.numeric(d$score))
c(n=sum(!is.na(d$score)),mean=mean(d$score,na.rm=TRUE),sd=sd(d$score,na.rm=TRUE),median=median(d$score,na.rm=TRUE))
hist(d$score)
