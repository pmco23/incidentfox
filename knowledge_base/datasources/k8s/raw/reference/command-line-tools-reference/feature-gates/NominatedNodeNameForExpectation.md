
When enabled, the kube-scheduler uses `.status.nominatedNodeName` to express where a
Pod is going to be bound.
External components can also write to `.status.nominatedNodeName` for a Pod to provide
a suggested placement.
