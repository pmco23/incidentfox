An {{< glossary_tooltip text="object" term_id="object" >}} that automatically scales the number of {{< glossary_tooltip term_id="pod" >}} replicas,
based on targeted {{< glossary_tooltip text="resource" term_id="infrastructure-resource" >}} utilization or custom metric targets.

<!--more--> 

HorizontalPodAutoscaler (HPA) is typically used with {{< glossary_tooltip text="Deployments" term_id="deployment" >}}, or {{< glossary_tooltip text="ReplicaSets" term_id="replica-set" >}}. It cannot be applied to objects that cannot be scaled, for example {{< glossary_tooltip text="DaemonSets" term_id="daemonset" >}}.

