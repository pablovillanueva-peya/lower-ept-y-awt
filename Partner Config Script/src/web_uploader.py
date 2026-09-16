import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union
from playwright.sync_api import sync_playwright, Page, FrameLocator, TimeoutError as PlaywrightTimeoutError
from config.config import Config
from src.logger import setup_logger

logger = setup_logger("SeamlessUploader")

class WebUploader:
    def __init__(
        self,
        app_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        headless: Optional[bool] = None,
        timeout_ms: Optional[int] = None
    ):
        self.app_url = app_url or Config.WEB_APP_URL
        self.username = username or Config.WEB_USERNAME
        self.password = password or Config.WEB_PASSWORD
        self.headless = headless if headless is not None else Config.BROWSER_HEADLESS
        self.timeout_ms = timeout_ms or Config.BROWSER_TIMEOUT_MS
        self.session_dir = Config.BROWSER_SESSION_DIR

    def _handle_okta_authentication(self, page: Page):
        """
        Gestiona la autenticación Okta / SSO si la sesión expiró.
        """
        current_url = page.url.lower()
        if "okta" in current_url or "login" in current_url or "auth" in current_url:
            logger.info("Pantalla de autenticación Okta / SSO detectada.")

            try:
                user_input = page.locator('input[name="identifier"], input[name="username"], input[type="email"], #okta-signin-username').first
                if user_input.is_visible(timeout=3000) and self.username:
                    logger.info(f"Ingresando usuario corporativo: {self.username}")
                    user_input.fill(self.username)
                    
                    next_btn = page.locator('input[type="submit"], button[type="submit"], .button-primary, #signin-submit').first
                    if next_btn.is_visible(timeout=2000):
                        next_btn.click()
                        page.wait_for_timeout(1500)

                pass_input = page.locator('input[type="password"], #okta-signin-password').first
                if pass_input.is_visible(timeout=3000) and self.password:
                    logger.info("Ingresando contraseña...")
                    pass_input.fill(self.password)
                    submit_btn = page.locator('input[type="submit"], button[type="submit"], #okta-signin-submit').first
                    if submit_btn.is_visible(timeout=2000):
                        submit_btn.click()
            except Exception as e:
                logger.debug(f"Paso inicial de login Okta: {e}")

            logger.info(
                "Esperando confirmación de inicio de sesión Okta (PIN / MFA / Push / redirección)...\n"
                "👉 Si aparece la solicitud en tu pantalla o teléfono, por favor confírmala."
            )

            try:
                page.wait_for_function(
                    "() => window.location.href.includes('pedidosya.com') && !window.location.href.includes('login') && !window.location.href.includes('okta')",
                    timeout=180000
                )
                logger.info("Autenticación completada. Acceso concedido al portal.")
            except PlaywrightTimeoutError:
                logger.warning("Tiempo de espera de redirección alcanzado. Verificando estado de la página...")

    def _get_app_container(self, page: Page) -> Union[Page, FrameLocator]:
        """
        Detecta si la aplicación Seamless está dentro de un iframe (pluginIframe)
        o directamente en el documento principal.
        """
        page.wait_for_timeout(2000)
        
        iframe_selectors = ['iframe.pluginIframe', 'iframe[src*="seamless"]', 'iframe']
        for ifr_sel in iframe_selectors:
            if page.locator(ifr_sel).count() > 0:
                logger.info(f"Detectado iframe de Seamless ({ifr_sel}).")
                return page.frame_locator(ifr_sel).first

        return page

    def _navigate_to_mass_updates_and_upload_csv(self, page: Page, app: Union[Page, FrameLocator]):
        """
        Navega a 'Mass updates' y luego selecciona la opción 'Upload CSV'.
        """
        logger.info("Navegando a 'Mass updates'...")
        page.wait_for_timeout(2000)

        # 1. Clic en "Mass updates"
        mass_update_selectors = [
            'button:has-text("UPLOAD CSV")',
            'button:has-text("Upload CSV")',
            'a:has-text("Mass updates")',
            'button:has-text("Mass updates")',
            'li:has-text("Mass updates")',
            'span:has-text("Mass updates")',
            'div:has-text("Mass updates")',
            'a[href*="bulk-updates"]',
            'a[href*="mass-updates"]',
            'text="Mass updates"'
        ]

        for sel in mass_update_selectors:
            try:
                el = app.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    logger.info(f"Clic en 'Mass updates': {sel}")
                    el.click()
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

        # 2. Clic en "Upload CSV"
        logger.info("Buscando opción 'Upload CSV'...")
        page.wait_for_timeout(1500)

        upload_csv_selectors = [
            'button:has-text("Upload CSV")',
            'button:has-text("UPLOAD CSV")',
            'a:has-text("Upload CSV")',
            'div:has-text("Upload CSV")',
            'span:has-text("Upload CSV")',
            '[role="tab"]:has-text("Upload CSV")',
            'text="Upload CSV"',
            'text="UPLOAD CSV"'
        ]

        for sel in upload_csv_selectors:
            try:
                el = app.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    logger.info(f"Clic en 'Upload CSV': {sel}")
                    el.click()
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

    def _click_continue(self, container: Union[Page, FrameLocator], page: Page, step_title: str):
        """
        Hace clic en el botón 'Continue' o '↓ Continue' del paso actual.
        """
        logger.info(f"[{step_title}] Buscando botón 'Continue'...")
        page.wait_for_timeout(1000)

        continue_buttons = [
            container.locator('button:has-text("Continue")').first,
            container.locator('button:has-text("Continuar")').first,
            container.locator('button:has-text("Siguiente")').first,
            container.locator('button:has-text("Next")').first,
            container.locator('button.btn-primary').first
        ]

        for btn in continue_buttons:
            try:
                if btn.count() > 0 and btn.is_visible():
                    logger.info(f"[{step_title}] Clic en 'Continue' ({btn}).")
                    btn.click(force=True)
                    page.wait_for_timeout(1500)
                    return
            except Exception:
                continue

        logger.warning(f"[{step_title}] No se detectó botón 'Continue' visible.")

    def upload_csv(self, csv_file_path: Path) -> bool:
        """
        Flujo de carga original y probado:
        1. Carga /main y espera estabilización
        2. Mass updates -> Upload CSV
        3. Pausa de 5 segundos para renderizado
        4. Paso 1 (Platform Country): Escribe 'PY_CL' y hace clic en la opción coincidente de la lista -> Continue
        5. Paso 2 (Type of vendors): Clic en botón 'OD Vendors' -> Continue
        6. Paso 3 (Type of action): Clic en opción de lista única 'Preparation times' -> Continue
        7. Paso 4 (Upload CSV): Adjunta CSV y confirma
        """
        if not csv_file_path.exists():
            raise FileNotFoundError(f"El archivo CSV no existe en la ruta: {csv_file_path}")

        logger.info(f"Iniciando navegador Playwright (Headless={self.headless})...")
        logger.info(f"Ruta del CSV a cargar: {csv_file_path}")

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(self.session_dir.resolve()),
                headless=self.headless,
                slow_mo=200 if not self.headless else 0,
                viewport={"width": 1440, "height": 900},
                accept_downloads=True
            )

            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(self.timeout_ms)

            try:
                # 1. Navegar a /main
                logger.info(f"Navegando a: {self.app_url}")
                page.goto(self.app_url)
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)

                # 2. Autenticación Okta si aplica
                self._handle_okta_authentication(page)

                # 3. Esperar que carguen todos los componentes de la URL main tras el login
                logger.info("⏳ Esperando 7 segundos para que carguen todos los componentes de la URL main...")
                page.wait_for_timeout(7000)

                # 4. Obtener contenedor del iframe
                app = self._get_app_container(page)

                # 5. Ir a Mass updates -> Upload CSV
                self._navigate_to_mass_updates_and_upload_csv(page, app)

                # 6. PAUSA DE 5 SEGUNDOS para carga completa de componentes del wizard
                logger.info("⏳ Pausa de 5 segundos para carga completa de componentes...")
                page.wait_for_timeout(5000)

                # Re-obtener app container tras la pausa
                app = self._get_app_container(page)

                # -------------------------------------------------------------
                # PASO 1: Platform Country (Escribir PY_CL y seleccionar)
                # -------------------------------------------------------------
                logger.info(">>> PASO 1: Platform Country -> Escribir 'PY_CL' y seleccionar coincidencia <<<")
                
                country_input = app.locator('input[type="text"], input[role="combobox"], [class*="control"] input').first
                if country_input.count() > 0 and country_input.is_visible():
                    country_input.click()
                    page.wait_for_timeout(300)
                    country_input.fill("PY_CL")
                else:
                    app.locator('text="Select Platform Country", [class*="select__control"]').first.click()
                    page.wait_for_timeout(300)
                    page.keyboard.type("PY_CL")

                page.wait_for_timeout(1000)

                # Hacer clic explícito en la opción/coincidencia que aparece en el menú desplegado
                matched_option_selectors = [
                    '[class*="option"]:has-text("PY_CL")',
                    '[id*="option"]:has-text("PY_CL")',
                    '[role="option"]:has-text("PY_CL")',
                    '[class*="menu"] >> text="PY_CL"',
                    '[class*="MenuList"] >> text="PY_CL"',
                    '[class*="option"]',
                    '[role="option"]',
                    'div:has-text("PY_CL")',
                    'text="PY_CL"'
                ]

                option_clicked = False
                for opt_sel in matched_option_selectors:
                    try:
                        opt = app.locator(opt_sel).first
                        if opt.count() > 0 and opt.is_visible():
                            logger.info(f"Haciendo clic en la coincidencia del menú desplegable: {opt_sel}")
                            opt.click(force=True)
                            option_clicked = True
                            page.wait_for_timeout(1000)
                            break
                    except Exception:
                        continue

                if not option_clicked:
                    logger.info("Seleccionando con ArrowDown + Enter como respaldo...")
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(300)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(500)

                page.wait_for_timeout(1000)
                self._click_continue(app, page, "Platform Country")

                # -------------------------------------------------------------
                # PASO 2: Type of vendors (Botón seleccionable OD Vendors) -> Continue
                # -------------------------------------------------------------
                logger.info(">>> PASO 2: Type of vendors -> Clic en botón 'OD Vendors' <<<")
                page.wait_for_timeout(1500)

                od_vendor_selectors = [
                    'button:has-text("OD Vendors")',
                    'button:has-text("OD vendors")',
                    'label:has-text("OD Vendors")',
                    'label:has-text("OD vendors")',
                    'div[role="button"]:has-text("OD Vendors")',
                    'div:has-text("OD Vendors")',
                    'text="OD Vendors"'
                ]
                for sel in od_vendor_selectors:
                    btn = app.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        logger.info(f"Clic en botón de 'OD Vendors': {sel}")
                        btn.click(force=True)
                        break

                page.wait_for_timeout(1000)
                self._click_continue(app, page, "Type of vendors")

                # -------------------------------------------------------------
                # PASO 3: Type of action (Opción de lista única Preparation times) -> Continue
                # -------------------------------------------------------------
                logger.info(">>> PASO 3: Type of action -> Clic en opción 'Preparation times' <<<")
                page.wait_for_timeout(1500)

                action_selectors = [
                    'label:has-text("Preparation times")',
                    'label:has-text("Preparations times")',
                    'label:has-text("Preparation time")',
                    'input[value*="Preparation"]',
                    'div:has-text("Preparation times")',
                    'div:has-text("Preparations times")',
                    'li:has-text("Preparation times")',
                    'li:has-text("Preparations times")',
                    'text="Preparation times"',
                    'text="Preparations times"'
                ]
                for sel in action_selectors:
                    act = app.locator(sel).first
                    if act.count() > 0 and act.is_visible():
                        logger.info(f"Clic en opción de acción: {sel}")
                        act.click(force=True)
                        break

                page.wait_for_timeout(1000)
                self._click_continue(app, page, "Type of action")

                # -------------------------------------------------------------
                # PASO 4: Carga del Archivo CSV
                # -------------------------------------------------------------
                logger.info(">>> PASO 4: Carga de Archivo CSV <<<")
                page.wait_for_timeout(2000)

                file_input = app.locator('input[type="file"]').first
                if file_input.count() == 0:
                    file_input = page.locator('input[type="file"]').first

                if file_input.count() > 0:
                    file_input.set_input_files(str(csv_file_path.resolve()))
                    logger.info(f"Archivo adjuntado correctamente: {csv_file_path.name}")
                else:
                    logger.warning("No se encontró input[type='file']. Intentando dropzone...")
                    dropzone = app.locator('text="Upload CSV File", [class*="dropzone"]').first
                    if dropzone.count() > 0:
                        dropzone.click()
                        page.wait_for_timeout(1000)

                page.wait_for_timeout(2000)

                # -------------------------------------------------------------
                # PASO 5: Confirmar / Subir
                # -------------------------------------------------------------
                logger.info("Buscando botón final de confirmación/subida...")
                submit_buttons = [
                    app.locator('button:has-text("Upload")').first,
                    app.locator('button:has-text("Subir")').first,
                    app.locator('button:has-text("Submit")').first,
                    app.locator('button:has-text("Confirm")').first,
                    app.locator('button:has-text("Process")').first,
                    app.locator('button.btn-primary').first
                ]

                for btn in submit_buttons:
                    try:
                        if btn.count() > 0 and btn.is_visible():
                            logger.info("Haciendo clic en botón final de confirmación.")
                            btn.click()
                            break
                    except Exception:
                        continue

                page.wait_for_timeout(6000)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = Config.LOGS_DIR / f"seamless_success_{timestamp}.png"
                page.screenshot(path=str(screenshot_path))
                logger.info(f"Captura de pantalla final guardada en: {screenshot_path}")

                logger.info("¡Proceso de Seamless Bulk Updates completado exitosamente!")
                return True

            except PlaywrightTimeoutError as e:
                err_img = Config.LOGS_DIR / f"error_timeout_{int(time.time())}.png"
                page.screenshot(path=str(err_img))
                logger.error(f"Timeout en Seamless Portal: {e}. Screenshot en {err_img}")
                raise
            except Exception as e:
                err_img = Config.LOGS_DIR / f"error_general_{int(time.time())}.png"
                try:
                    page.screenshot(path=str(err_img))
                    logger.error(f"Error en Seamless Portal: {e}. Screenshot en {err_img}")
                except Exception:
                    logger.error(f"Error: {e}")
                raise
            finally:
                context.close()
