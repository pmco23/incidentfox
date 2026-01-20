 Preemption logic in Kubernetes helps a pending {{< glossary_tooltip term_id="pod" >}} to find a suitable {{< glossary_tooltip term_id="node" >}} by evicting low priority Pods existing on that Node.

<!--more-->

If a Pod cannot be scheduled, the scheduler tries to [preempt](/docs/concepts/scheduling-eviction/pod-priority-preemption/#preemption) lower priority Pods to make scheduling of the pending Pod possible.
