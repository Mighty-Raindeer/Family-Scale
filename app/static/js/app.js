(function () {
  const addPanel = document.getElementById("add-person-panel");
  const toggleAdd = document.getElementById("toggle-add-person");
  const cancelAdd = document.getElementById("cancel-add-person");
  const personChips = document.querySelectorAll(".person-chip[data-person]");

  function showAdd(show) {
    if (!addPanel) return;
    addPanel.hidden = !show;
    addPanel.classList.toggle("is-hidden", !show);
  }

  if (toggleAdd) {
    toggleAdd.addEventListener("click", function () {
      showAdd(true);
      const name = addPanel.querySelector('input[name="name"]');
      if (name) name.focus();
    });
  }
  if (cancelAdd) {
    cancelAdd.addEventListener("click", function () {
      showAdd(false);
    });
  }

  personChips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      try {
        localStorage.setItem("fs-person", chip.getAttribute("data-person"));
      } catch (err) {
        /* ignore */
      }
    });
  });

  document.querySelectorAll(".kind-pills a").forEach(function (link) {
    link.addEventListener("click", function () {
      try {
        const kind = new URL(link.href, window.location.origin).searchParams.get("kind");
        if (kind) localStorage.setItem("fs-kind", kind);
      } catch (err) {
        /* ignore */
      }
    });
  });

  if (window.location.pathname === "/" && !/person=/.test(window.location.search)) {
    try {
      const saved = localStorage.getItem("fs-person");
      const match = saved && document.querySelector('.person-chip[data-person="' + saved + '"]');
      if (match && !match.classList.contains("is-selected")) {
        window.location.replace(match.getAttribute("href"));
        return;
      }
    } catch (err) {
      /* ignore */
    }
  }

  const intervalSome = document.getElementById("interval-some");
  document.querySelectorAll('input[name="interval"]').forEach(function (radio) {
    radio.addEventListener("change", function () {
      if (!intervalSome) return;
      intervalSome.hidden = radio.value !== "some";
    });
  });

  const filters = document.getElementById("progress-filters");
  if (filters) {
    filters.addEventListener("change", function () {
      filters.submit();
    });
  }

  const cfg = window.FS_PROGRESS;
  const canvas = document.getElementById("weight-chart");
  if (cfg && canvas && window.Chart) {
    fetch(cfg.api)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        const points = data.points || [];
        const hasWeight = points.some(function (p) { return p.weight != null; });
        const hasWaist = points.some(function (p) { return p.waist != null; });
        const hasAvg = points.filter(function (p) { return p.average != null; }).length >= 2;
        const datasets = [];

        if (hasWeight) {
          datasets.push({
            label: "Weight",
            data: points.map(function (p) { return p.weight; }),
            borderColor: data.color,
            backgroundColor: data.color + "22",
            fill: !hasAvg,
            tension: 0.25,
            spanGaps: true,
            pointRadius: 4,
            pointBackgroundColor: points.map(function (p) {
              return p.fasting ? data.color : "#fff";
            }),
            pointBorderColor: data.color,
            pointBorderWidth: 2,
            yAxisID: "y"
          });
        }
        if (hasAvg) {
          datasets.push({
            label: "7-day avg",
            data: points.map(function (p) { return p.average; }),
            borderColor: "#8a7d6b",
            borderDash: [5, 4],
            pointRadius: 0,
            tension: 0.3,
            spanGaps: true,
            fill: false,
            yAxisID: "y"
          });
        }
        if (hasWaist) {
          datasets.push({
            label: "Waist",
            data: points.map(function (p) { return p.waist; }),
            borderColor: "#c45c26",
            backgroundColor: "transparent",
            tension: 0.25,
            spanGaps: true,
            pointRadius: 3,
            yAxisID: hasWeight ? "y1" : "y"
          });
        }

        function sameDay(a, b) {
          return a && b && a.toDateString() === b.toDateString();
        }
        const scales = {
          x: {
            ticks: {
              callback: function (value, index) {
                const raw = points[index];
                if (!raw) return "";
                const when = new Date(raw.at);
                const prev = points[index - 1] && new Date(points[index - 1].at);
                const next = points[index + 1] && new Date(points[index + 1].at);
                const showTime = sameDay(when, prev) || sameDay(when, next);
                if (showTime) {
                  return when.toLocaleString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit"
                  });
                }
                return when.toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric"
                });
              },
              maxRotation: 0,
              autoSkip: true,
              maxTicksLimit: 8
            },
            grid: { display: false }
          },
          y: {
            title: { display: true, text: hasWeight ? data.unit_label : data.waist_unit },
            grace: "8%"
          }
        };
        if (hasWeight && hasWaist) {
          scales.y1 = {
            position: "right",
            title: { display: true, text: data.waist_unit },
            grace: "8%",
            grid: { drawOnChartArea: false }
          };
        }

        new window.Chart(canvas, {
          type: "line",
          data: { labels: points.map(function (p) { return p.at; }), datasets: datasets },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: datasets.length > 1 },
              tooltip: {
                callbacks: {
                  title: function (items) {
                    const raw = items[0] && points[items[0].dataIndex];
                    if (!raw) return "";
                    return new Date(raw.at).toLocaleString();
                  }
                }
              }
            },
            scales: scales
          }
        });
      })
      .catch(function () {
        canvas.replaceWith(Object.assign(document.createElement("p"), {
          className: "hint",
          textContent: "Could not load the chart."
        }));
      });
  }

  const milesCanvas = document.getElementById("miles-chart");
  if (cfg && milesCanvas && cfg.milesApi && window.Chart) {
    fetch(cfg.milesApi)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        const weeks = data.weeks || [];
        if (!weeks.length) return;
        new window.Chart(milesCanvas, {
          type: "bar",
          data: {
            labels: weeks.map(function (w) { return w.week; }),
            datasets: [{
              label: data.unit,
              data: weeks.map(function (w) { return w.distance; }),
              backgroundColor: (data.color || "#1f6b57") + "99",
              borderRadius: 8
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: function (item) {
                    return item.formattedValue + " " + data.unit;
                  }
                }
              }
            },
            scales: {
              x: {
                ticks: {
                  callback: function (value, index) {
                    const raw = weeks[index];
                    if (!raw) return "";
                    return new Date(raw.week + "T00:00:00").toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric"
                    });
                  }
                },
                grid: { display: false }
              },
              y: {
                title: { display: true, text: data.unit },
                beginAtZero: true
              }
            }
          }
        });
      })
      .catch(function () { /* leave empty */ });
  }

  const setList = document.getElementById("set-list");
  const addSet = document.getElementById("add-set");
  if (setList && addSet) {
    addSet.addEventListener("click", function () {
      const row = document.createElement("div");
      row.className = "set-row";
      row.innerHTML =
        '<input type="text" name="set_name" list="exercise-list" placeholder="Squat">' +
        '<input type="number" name="set_reps" min="1" max="200" step="1" placeholder="8">' +
        '<input type="number" name="set_weight" min="0" max="800" step="0.5">';
      setList.appendChild(row);
      row.querySelector("input").focus();
    });
  }
})();
