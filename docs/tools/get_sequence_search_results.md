# `get_sequence_search_results`

Check on a sequence search started with {doc}`search_sequence`. Returns progress while the
job is running, and a summary of the top hits once it has finished.

## Arguments

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `job_id` | `str` | yes | The job ID returned by `search_sequence`. |

## Returns

One of:

- a progress line (`pending` or `running`, percent complete, databases finished);
- a note that the job finished but its hits are not available yet (see below);
- a markdown summary of the top five hits with score, E-value, identity and query
  coverage, plus the total hit count;
- an error message if the job failed or was not found.

## Notes

- Each call is a single quick check; it does not wait. Call it again after 30–60 seconds
  if the job is still running. Under load a search can take minutes to hours.
- The service marks a job `finished` about 20 seconds before the hits can be read, so a
  finished job may report no hits once. If a second check is still empty, there are no
  matches.
- Job results are kept by the service for a limited time, so fetch them soon after the job
  finishes.
