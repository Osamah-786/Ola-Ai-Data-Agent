const steps = [
  { number: "01", title: "Describe the task", text: "Use plain language or start with an example." },
  { number: "02", title: "Submit the request", text: "The API validates the message and responds." },
  { number: "03", title: "Inspect the response", text: "See the result mode and any available details." },
];

export function WorkflowGuide() {
  return (
    <section className="workflow-guide" aria-labelledby="workflow-title">
      <div className="workflow-guide__heading">
        <span className="workflow-guide__overline">HOW IT WORKS</span>
        <h2 id="workflow-title">A simple path from question to response</h2>
      </div>
      <ol className="workflow-steps">
        {steps.map((step) => (
          <li className="workflow-step" key={step.number}>
            <span className="workflow-step__number">{step.number}</span>
            <div>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
