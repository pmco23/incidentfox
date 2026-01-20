 A ReplicaSet (aims to) maintain a set of replica Pods running at any given time.

<!--more-->

Workload objects such as {{< glossary_tooltip term_id="deployment" >}} make use of ReplicaSets
to ensure that the configured number of {{< glossary_tooltip term_id="pod" text="Pods" >}} are
running in your cluster, based on the spec of that ReplicaSet.
