# Shared teaching artifact writer. Numbers are computed, never manually inserted.
finish <- function(metrics, tables=list(), valid=TRUE) {
  stopifnot(all(is.finite(unlist(metrics))))
  jsonlite::write_json(list(metrics=as.list(metrics), tables=tables,
                            figures=list(), valid=valid), "result.json",
                       auto_unbox=TRUE, digits=16, pretty=TRUE)
}

# Continuous teaching indicators; no real participant data.
latent_teaching <- function(n=400, seed=4301) {
  set.seed(seed)
  f1 <- rnorm(n); f2 <- 0.3*f1+rnorm(n,sd=sqrt(0.91))
  f3 <- 0.4*f1+0.3*f2+rnorm(n,sd=0.8)
  factors <- list(f1,f2,f3)
  d <- as.data.frame(sapply(1:9,function(j) {
    0.8*factors[[ceiling(j/3)]]+rnorm(n,sd=0.6)
  }))
  names(d) <- paste0("x",1:9)
  d
}

measurement_model <- 'f1 =~ x1+x2+x3
 f2 =~ x4+x5+x6
 f3 =~ x7+x8+x9'

check_sem <- function(fit) {
  stopifnot(lavaan::lavInspect(fit,"converged"))
  pe <- lavaan::parameterEstimates(fit)
  diagonal <- pe$op=="~~" & pe$lhs==pe$rhs
  stopifnot(all(pe$est[diagonal]>=0),lavaan::lavInspect(fit,"post.check"))
  invisible(pe)
}

sem_tables <- function(fit) {
  list(parameters=lavaan::parameterEstimates(fit,standardized=TRUE),
       fit=data.frame(index=names(lavaan::fitMeasures(fit)),value=as.numeric(lavaan::fitMeasures(fit))))
}
