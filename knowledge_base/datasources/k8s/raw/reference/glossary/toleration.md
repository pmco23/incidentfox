 A core object consisting of three required properties: key, value, and effect. Tolerations enable the scheduling of pods on nodes or node groups that have matching {{< glossary_tooltip text="taints" term_id="taint" >}}.

<!--more-->

Tolerations and {{< glossary_tooltip text="taints" term_id="taint" >}} work together to ensure that pods are not scheduled onto inappropriate nodes. One or more tolerations are applied to a {{< glossary_tooltip text="pod" term_id="pod" >}}. A toleration indicates that the {{< glossary_tooltip text="pod" term_id="pod" >}} is allowed (but not required) to be scheduled on nodes or node groups with matching {{< glossary_tooltip text="taints" term_id="taint" >}}.
