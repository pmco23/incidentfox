In Kubernetes, controllers are control loops that watch the state of your
{{< glossary_tooltip term_id="cluster" text="cluster">}}, then make or request
changes where needed.
Each controller tries to move the current cluster state closer to the desired
state.

<!--more-->

Controllers watch the shared state of your cluster through the
{{< glossary_tooltip text="apiserver" term_id="kube-apiserver" >}} (part of the
{{< glossary_tooltip term_id="control-plane" >}}).

Some controllers also run inside the control plane, providing control loops that
are core to Kubernetes' operations. For example: the deployment controller, the
daemonset controller, the namespace controller, and the persistent volume
controller (and others) all run within the
{{< glossary_tooltip term_id="kube-controller-manager" >}}.
