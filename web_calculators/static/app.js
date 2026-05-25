/**
 * HVAC Calculators - Frontend Application
 * Handles form submissions, API calls, and UI interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    // Tab navigation
    const tabButtons = document.querySelectorAll('.tab-btn');
    const calculatorSections = document.querySelectorAll('.calculator');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const calculatorId = button.dataset.calculator;

            // Update active tab
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            // Show corresponding calculator section
            calculatorSections.forEach(section => {
                section.classList.remove('active');
                if (section.id === calculatorId) {
                    section.classList.add('active');
                }
            });
        });
    });

    // Form handling for each calculator
    const forms = document.querySelectorAll('.calc-form');

    forms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const calculatorSection = form.closest('.calculator');
            const calculatorId = calculatorSection.id;
            const resultsDiv = document.getElementById(`${calculatorId}-results`);
            const submitBtn = form.querySelector('.calculate-btn');

            // Show loading state
            submitBtn.disabled = true;
            submitBtn.classList.add('loading');
            resultsDiv.innerHTML = '<p class="placeholder">Calculating...</p>';

            try {
                // Gather form data
                const formData = new FormData(form);
                const data = Object.fromEntries(formData.entries());

                // Handle conditional fields for fan and pump calculators
                if (calculatorId === 'fan') {
                    const calcType = data.calculation_type;
                    if (calcType === 'cfm') {
                        data.cfm_2 = parseFloat(data.cfm_2);
                    } else {
                        data.rpm_2 = parseFloat(data.rpm_2);
                    }
                } else if (calculatorId === 'pump') {
                    const calcType = data.calculation_type;
                    if (calcType === 'gpm') {
                        data.gpm_2 = parseFloat(data.gpm_2);
                    } else {
                        data.rpm_2 = parseFloat(data.rpm_2);
                    }
                }

                // Convert numeric fields
                const numericFields = ['conduit_size', 'wire_gauge', 'num_wires', 'flow_rate_gpm',
                    'max_velocity_fps', 'max_pressure_drop', 'airflow_cfm', 'duct_width_in',
                    'duct_height_in', 'length_ft', 'cfm_1', 'rpm_1', 'bhp_1', 'gpm_1', 'head_1'];

                numericFields.forEach(field => {
                    if (data[field] !== undefined) {
                        data[field] = parseFloat(data[field]);
                    }
                });

                // Make API call
                const response = await fetch(`/api/calculate/${calculatorId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data),
                });

                const result = await response.json();

                if (result.success) {
                    displayResults(resultsDiv, result.data, calculatorId);
                } else {
                    displayError(resultsDiv, result.error);
                }
            } catch (error) {
                displayError(resultsDiv, `Request failed: ${error.message}`);
            } finally {
                // Remove loading state
                submitBtn.disabled = false;
                submitBtn.classList.remove('loading');
            }
        });
    });

    // Handle fan calculator type switching
    const fanCalcType = document.getElementById('fan_calc_type');
    if (fanCalcType) {
        fanCalcType.addEventListener('change', (e) => {
            const cfmGroup = document.querySelector('.fan-condition[data-type="cfm"]');
            const rpmGroup = document.querySelector('.fan-condition[data-type="rpm"]');

            if (e.target.value === 'cfm') {
                cfmGroup.style.display = 'flex';
                rpmGroup.style.display = 'none';
            } else {
                cfmGroup.style.display = 'none';
                rpmGroup.style.display = 'flex';
            }
        });
    }

    // Handle pump calculator type switching
    const pumpCalcType = document.getElementById('pump_calc_type');
    if (pumpCalcType) {
        pumpCalcType.addEventListener('change', (e) => {
            const gpmGroup = document.querySelector('.pump-condition[data-type="gpm"]');
            const rpmGroup = document.querySelector('.pump-condition[data-type="rpm"]');

            if (e.target.value === 'gpm') {
                gpmGroup.style.display = 'flex';
                rpmGroup.style.display = 'none';
            } else {
                gpmGroup.style.display = 'none';
                rpmGroup.style.display = 'flex';
            }
        });
    }
});

/**
 * Display calculation results
 * @param {HTMLElement} container - Results container div
 * @param {Object} data - Result data from API
 * @param {string} calculatorId - ID of the calculator
 */
function displayResults(container, data, calculatorId) {
    let html = '';

    // Format results based on calculator type
    switch (calculatorId) {
        case 'conduit':
            html = `
                <div class="result-item">
                    <div class="result-label">Fill Percentage</div>
                    <div class="result-value">${(data.fill_percentage * 100).toFixed(1)}<span class="result-unit">%</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">NEC Limit (40%)</div>
                    <div class="result-value">${(data.nec_limit * 100).toFixed(1)}<span class="result-unit">%</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">Status</div>
                    <div class="result-value" style="color: ${data.compliant ? 'var(--success-color)' : 'var(--error-color)'}">
                        ${data.compliant ? '✓' : '✗'} ${data.compliant ? 'Compliant' : 'Overfilled'}
                    </div>
                </div>
                <div class="result-note">
                    <strong>Recommended:</strong> ${data.recommended_size ? data.recommended_size + ' conduit' : 'N/A'}
                </div>
            `;
            break;

        case 'pipe':
            html = `
                <div class="result-item">
                    <div class="result-label">Nominal Size</div>
                    <div class="result-value">${data.nominal_size}<span class="result-unit">${data.size_unit}</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">Actual ID</div>
                    <div class="result-value">${data.actual_id.toFixed(3)}<span class="result-unit">${data.size_unit}</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">Velocity</div>
                    <div class="result-value">${data.velocity.toFixed(2)}<span class="result-unit">ft/s</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">Pressure Drop</div>
                    <div class="result-value">${data.pressure_drop.toFixed(2)}<span class="result-unit">ft/100ft</span></div>
                </div>
                ${data.velocity_warning ? '<div class="result-note"><strong>Warning:</strong> Velocity exceeds recommended maximum</div>' : ''}
                ${data.pressure_drop_warning ? '<div class="result-note"><strong>Warning:</strong> Pressure drop exceeds recommended maximum</div>' : ''}
            `;
            break;

        case 'duct':
            html = `
                <div class="result-item">
                    <div class="result-label">Equivalent Diameter</div>
                    <div class="result-value">${data.equivalent_diameter.toFixed(2)}<span class="result-unit">in</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">Velocity</div>
                    <div class="result-value">${data.velocity_fpm.toFixed(0)}<span class="result-unit">ft/min</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">Pressure Drop</div>
                    <div class="result-value">${data.pressure_drop.toFixed(3)}<span class="result-unit">in H2O</span></div>
                </div>
                <div class="result-note">
                    Calculated using Huebscher equation for rectangular ducts
                </div>
            `;
            break;

        case 'fan':
            html = `
                <div class="result-item">
                    <div class="result-label">New CFM</div>
                    <div class="result-value">${data.cfm_2.toFixed(0)}<span class="result-unit">CFM</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">New RPM</div>
                    <div class="result-value">${data.rpm_2.toFixed(0)}<span class="result-unit">RPM</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">New BHP</div>
                    <div class="result-value">${data.bhp_2.toFixed(2)}<span class="result-unit">BHP</span></div>
                </div>
                <div class="result-note">
                    Fan Laws: CFM ∝ RPM, Pressure ∝ RPM², BHP ∝ RPM³
                </div>
            `;
            break;

        case 'pump':
            html = `
                <div class="result-item">
                    <div class="result-label">New GPM</div>
                    <div class="result-value">${data.gpm_2.toFixed(0)}<span class="result-unit">GPM</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">New RPM</div>
                    <div class="result-value">${data.rpm_2.toFixed(0)}<span class="result-unit">RPM</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">New Head</div>
                    <div class="result-value">${data.head_2.toFixed(1)}<span class="result-unit">ft</span></div>
                </div>
                <div class="result-item">
                    <div class="result-label">New BHP</div>
                    <div class="result-value">${data.bhp_2.toFixed(2)}<span class="result-unit">BHP</span></div>
                </div>
                <div class="result-note">
                    Pump Affinity Laws: GPM ∝ RPM, Head ∝ RPM², BHP ∝ RPM³
                </div>
            `;
            break;

        default:
            html = '<p class="placeholder">Unknown calculator type</p>';
    }

    container.innerHTML = html;
}

/**
 * Display error message
 * @param {HTMLElement} container - Results container div
 * @param {string} message - Error message
 */
function displayError(container, message) {
    container.innerHTML = `
        <div class="result-error">
            ⚠️ ${message}
        </div>
    `;
}
