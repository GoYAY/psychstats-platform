d <- read.csv("your_data.csv",stringsAsFactors=FALSE)
colSums(is.na(d)); colMeans(is.na(d))
# Inspect patterns and study context before choosing complete cases or imputation.
