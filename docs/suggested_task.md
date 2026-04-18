# Title: Implement Dynamic Agent Scaling Based on Workload

## Description:
The Cognitive Foundry swarm currently operates with a fixed single orchestrator agent. This task implements dynamic agent scaling that automatically adjusts the number of active agent instances based on real-time workload metrics such as queue depth, processing latency, and system load.

## Acceptance Criteria:
1. Add a workload monitoring module that tracks:
   - Number of pending prompts in the queue
   - Average processing time per prompt
   - Current number of active agent instances

2. Implement scaling rules:
   - Scale up: Add new agent instances when queue depth exceeds threshold (e.g., >5 pending prompts)
   - Scale down: Remove idle agent instances when queue is empty for a sustained period (e.g., >30 seconds)
   - Minimum 1 agent always running, maximum configurable limit

3. Create a scaling manager service that:
   - Monitors workload metrics at regular intervals
   - Makes scaling decisions based on defined thresholds
   - Spawns/terminates agent instances as needed
   - Maintains load distribution across active instances

4. Ensure graceful handling:
   - No disruption to ongoing prompts during scaling
   - Proper cleanup of terminated agent instances
   - Logging of all scaling events for observability

5. Add configuration options:
   - Queue depth threshold for scale-up
   - Idle timeout for scale-down
   - Minimum and maximum agent count limits
   - Scaling check interval duration