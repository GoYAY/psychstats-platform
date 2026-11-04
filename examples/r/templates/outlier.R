d <- read.csv("your_data.csv")
stopifnot(is.numeric(d$score))
q <- quantile(d$score,c(.25,.75),na.rm=TRUE); iqr <- diff(q)
d$outlier_flag <- !is.na(d$score) & (d$score < q[1]-1.5*iqr | d$score > q[2]+1.5*iqr)
table(d$outlier_flag); d[d$outlier_flag, ]
# Check entry errors and context; do not delete flagged cases automatically.
