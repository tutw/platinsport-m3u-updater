const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const { parseString, Builder } = require('xml2js');

class ProductionStreamingScraperComplete {
    constructor() {
        this.browser = null;
        this.results = [];
        this.processed = 0;
        this.errors = 0;
        this.startTime = null;
        this.totalEvents = 0;
        this.stats = {
            success: 0,
            failed: 0,
            linksExtracted: 0,
            averageLinksPerEvent: 0
        };

        // Configuración optimizada para procesamiento masivo
        this.config = {
            headless: true,
            timeout: 45000, // Aumentado para eventos complejos
            maxRetries: 3,
            delay: { min: 3000, max: 7000 }, // Más conservador para evitar bloqueos
            batchSize: 5, // Reducido para estabilidad
            maxConcurrent: 3, // Procesamiento concurrente controlado
            saveInterval: 50, // Guardar progreso cada 50 eventos
            userAgents: [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0'
            ]
        };
    }

    async init() {
        console.log('🚀 Iniciando navegador optimizado para procesamiento masivo...');
        this.startTime = Date.now();
        
        this.browser = await puppeteer.launch({
            headless: this.config.headless,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1920x1080',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images', // Optimización: no cargar imágenes
                '--disable-javascript-harmony-shipping',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
            ],
            defaultViewport: { width: 1920, height: 1080 }
        });

        console.log('✅ Navegador iniciado correctamente');
    }

    async downloadXML() {
        console.log('📥 Descargando XML desde GitHub...');
        const xmlUrl = 'https://raw.githubusercontent.com/tutw/platinsport-m3u-updater/refs/heads/main/eventos_livetv_sx.xml';
        
        try {
            const response = await fetch(xmlUrl);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const xmlContent = await response.text();
            console.log('✅ XML descargado correctamente');
            return xmlContent;
        } catch (error) {
            console.error('❌ Error descargando XML:', error);
            throw error;
        }
    }

    async parseXML(xmlContent) {
        return new Promise((resolve, reject) => {
            parseString(xmlContent, (err, result) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(result);
                }
            });
        });
    }

    getRandomUserAgent() {
        return this.config.userAgents[Math.floor(Math.random() * this.config.userAgents.length)];
    }

    async randomDelay() {
        const delay = Math.random() * (this.config.delay.max - this.config.delay.min) + this.config.delay.min;
        await new Promise(resolve => setTimeout(resolve, delay));
    }

    async extractStreamingLinks(eventUrl, retryCount = 0) {
        let page = null;
        try {
            page = await this.browser.newPage();
            
            // Configurar User-Agent aleatorio
            await page.setUserAgent(this.getRandomUserAgent());
            
            // Configurar timeouts y opciones
            await page.setDefaultTimeout(this.config.timeout);
            await page.setDefaultNavigationTimeout(this.config.timeout);
            
            // Interceptar y bloquear recursos innecesarios
            await page.setRequestInterception(true);
            page.on('request', (req) => {
                const resourceType = req.resourceType();
                if (['image', 'stylesheet', 'font', 'media'].includes(resourceType)) {
                    req.abort();
                } else {
                    req.continue();
                }
            });

            console.log(`🔍 Procesando: ${eventUrl}`);
            
            // Navegar con opciones robustas
            await page.goto(eventUrl, {
                waitUntil: 'domcontentloaded',
                timeout: this.config.timeout
            });

            // Esperar a que la página se cargue completamente
            await page.waitForTimeout(3000);

            // Extraer enlaces del DOM
            const streamingLinks = await page.evaluate(() => {
                const links = [];
                
                // Buscar en #links_block
                const linksBlock = document.querySelector('#links_block');
                if (linksBlock) {
                    const anchors = linksBlock.querySelectorAll('a[href]');
                    anchors.forEach(anchor => {
                        const href = anchor.href;
                        if (href && (
                            href.includes('cdn') || 
                            href.includes('stream') || 
                            href.includes('player') ||
                            href.includes('live') ||
                            href.includes('embed') ||
                            href.includes('watch')
                        )) {
                            links.push({
                                url: href,
                                type: href.includes('youtube') ? 'youtube' : 
                                     href.includes('cdn') ? 'cdn' : 
                                     href.includes('player') ? 'webplayer' : 'stream',
                                text: anchor.textContent?.trim() || ''
                            });
                        }
                    });
                }

                // Buscar iframes
                const iframes = document.querySelectorAll('iframe[src]');
                iframes.forEach(iframe => {
                    const src = iframe.src;
                    if (src && (
                        src.includes('embed') || 
                        src.includes('player') || 
                        src.includes('stream') ||
                        src.includes('cdn')
                    )) {
                        links.push({
                            url: src,
                            type: src.includes('youtube') ? 'youtube' : 
                                 src.includes('player') ? 'webplayer' : 'iframe',
                            text: 'iframe'
                        });
                    }
                });

                // Buscar enlaces adicionales en el DOM
                const allLinks = document.querySelectorAll('a[href*="stream"], a[href*="player"], a[href*="live"], a[href*="cdn"]');
                allLinks.forEach(link => {
                    const href = link.href;
                    if (href && !links.some(l => l.url === href)) {
                        links.push({
                            url: href,
                            type: 'additional',
                            text: link.textContent?.trim() || ''
                        });
                    }
                });

                return links;
            });

            await page.close();
            
            console.log(`✅ Extraídos ${streamingLinks.length} enlaces de: ${eventUrl}`);
            this.stats.linksExtracted += streamingLinks.length;
            
            return {
                success: true,
                links: streamingLinks,
                attempts: retryCount + 1
            };

        } catch (error) {
            if (page) await page.close();
            
            console.error(`❌ Error en ${eventUrl}: ${error.message}`);
            
            if (retryCount < this.config.maxRetries) {
                console.log(`🔄 Reintentando (${retryCount + 1}/${this.config.maxRetries})...`);
                await this.randomDelay();
                return this.extractStreamingLinks(eventUrl, retryCount + 1);
            }
            
            return {
                success: false,
                links: [],
                attempts: retryCount + 1,
                error: error.message
            };
        }
    }

    async processBatch(events, batchIndex) {
        console.log(`📦 Procesando lote ${batchIndex + 1} (${events.length} eventos)...`);
        
        const results = [];
        
        for (let i = 0; i < events.length; i++) {
            const event = events[i];
            const result = await this.extractStreamingLinks(event.url[0]);
            
            results.push({
                ...event,
                streaming_links: {
                    $: {
                        extracted_at: new Date().toISOString(),
                        success: result.success.toString(),
                        attempts: result.attempts.toString(),
                        links_count: result.links.length.toString()
                    },
                    url: result.links.map(link => ({
                        $: { type: link.type },
                        _: link.url
                    }))
                }
            });
            
            this.processed++;
            
            if (result.success) {
                this.stats.success++;
            } else {
                this.stats.failed++;
            }
            
            // Progreso cada 10 eventos
            if (this.processed % 10 === 0) {
                const progress = ((this.processed / this.totalEvents) * 100).toFixed(1);
                const elapsed = ((Date.now() - this.startTime) / 1000 / 60).toFixed(1);
                console.log(`📊 Progreso: ${this.processed}/${this.totalEvents} (${progress}%) - ${elapsed}min`);
            }
            
            // Guardar progreso intermedio
            if (this.processed % this.config.saveInterval === 0) {
                await this.saveProgressFile(results);
            }
            
            // Delay entre eventos
            await this.randomDelay();
        }
        
        return results;
    }

    async saveProgressFile(currentResults) {
        try {
            const progressData = {
                timestamp: new Date().toISOString(),
                processed: this.processed,
                total: this.totalEvents,
                progress: ((this.processed / this.totalEvents) * 100).toFixed(2),
                stats: this.stats,
                events: currentResults
            };
            
            await fs.promises.writeFile(
                `progreso_scraper_${Date.now()}.json`,
                JSON.stringify(progressData, null, 2)
            );
            
            console.log(`💾 Progreso guardado: ${this.processed}/${this.totalEvents} eventos`);
        } catch (error) {
            console.error('❌ Error guardando progreso:', error);
        }
    }

    async generateFinalXML(allResults) {
        const xmlBuilder = new Builder({
            xmldec: { version: '1.0', encoding: 'utf-8' }
        });

        const finalXML = {
            eventos: {
                $: {
                    generado: new Date().toISOString().split('T')[0] + ' ' + 
                             new Date().toISOString().split('T')[1].split('.')[0],
                    total: allResults.length.toString(),
                    processed_by: 'ProductionStreamingScraperComplete',
                    processing_time: ((Date.now() - this.startTime) / 1000 / 60).toFixed(2) + ' minutes',
                    success_rate: ((this.stats.success / this.totalEvents) * 100).toFixed(2) + '%',
                    total_links_extracted: this.stats.linksExtracted.toString()
                },
                evento: allResults
            }
        };

        return xmlBuilder.buildObject(finalXML);
    }

    async scrapeAllEvents() {
        try {
            console.log('🎯 Iniciando scraping completo de todos los eventos...');
            
            // Descargar y parsear XML
            const xmlContent = await this.downloadXML();
            const parsedXML = await this.parseXML(xmlContent);
            const events = parsedXML.eventos.evento;
            
            this.totalEvents = events.length;
            console.log(`📊 Total de eventos a procesar: ${this.totalEvents}`);
            
            // Procesar en lotes
            const allResults = [];
            const batches = [];
            
            for (let i = 0; i < events.length; i += this.config.batchSize) {
                batches.push(events.slice(i, i + this.config.batchSize));
            }
            
            console.log(`📦 Procesando ${batches.length} lotes de ${this.config.batchSize} eventos cada uno`);
            
            for (let i = 0; i < batches.length; i++) {
                const batchResults = await this.processBatch(batches[i], i);
                allResults.push(...batchResults);
                
                // Pausa entre lotes para evitar sobrecarga
                if (i < batches.length - 1) {
                    console.log('⏸️ Pausa entre lotes...');
                    await new Promise(resolve => setTimeout(resolve, 5000));
                }
            }
            
            // Calcular estadísticas finales
            this.stats.averageLinksPerEvent = (this.stats.linksExtracted / this.totalEvents).toFixed(2);
            
            // Generar XML final
            console.log('📝 Generando XML final...');
            const finalXML = await this.generateFinalXML(allResults);
            
            // Guardar archivo final
            const filename = `eventos_con_streaming_completo_${Date.now()}.xml`;
            await fs.promises.writeFile(filename, finalXML);
            
            // Generar reporte final
            const report = {
                timestamp: new Date().toISOString(),
                totalEvents: this.totalEvents,
                processed: this.processed,
                stats: this.stats,
                processingTime: ((Date.now() - this.startTime) / 1000 / 60).toFixed(2) + ' minutes',
                filename: filename,
                summary: {
                    successRate: ((this.stats.success / this.totalEvents) * 100).toFixed(2) + '%',
                    averageLinksPerEvent: this.stats.averageLinksPerEvent,
                    totalLinksExtracted: this.stats.linksExtracted,
                    eventsWithLinks: this.stats.success,
                    eventsWithoutLinks: this.stats.failed
                }
            };
            
            await fs.promises.writeFile(
                `reporte_scraping_completo_${Date.now()}.json`,
                JSON.stringify(report, null, 2)
            );
            
            console.log('🎉 SCRAPING COMPLETO FINALIZADO!');
            console.log(`📊 Estadísticas Finales:`);
            console.log(`   - Eventos procesados: ${this.processed}/${this.totalEvents}`);
            console.log(`   - Tasa de éxito: ${((this.stats.success / this.totalEvents) * 100).toFixed(2)}%`);
            console.log(`   - Enlaces extraídos: ${this.stats.linksExtracted}`);
            console.log(`   - Promedio enlaces/evento: ${this.stats.averageLinksPerEvent}`);
            console.log(`   - Tiempo total: ${((Date.now() - this.startTime) / 1000 / 60).toFixed(2)} minutos`);
            console.log(`   - Archivo generado: ${filename}`);
            
            return report;
            
        } catch (error) {
            console.error('💥 Error en scraping completo:', error);
            throw error;
        }
    }

    async close() {
        if (this.browser) {
            await this.browser.close();
            console.log('🔒 Navegador cerrado');
        }
    }
}

// Función principal para ejecutar el scraper completo
async function runCompleteProductionScraper() {
    const scraper = new ProductionStreamingScraperComplete();
    
    try {
        await scraper.init();
        const report = await scraper.scrapeAllEvents();
        await scraper.close();
        
        console.log('✅ Proceso completo exitoso');
        return report;
        
    } catch (error) {
        console.error('❌ Error en proceso completo:', error);
        await scraper.close();
        throw error;
    }
}

// Para ejecutar desde línea de comandos
if (require.main === module) {
    runCompleteProductionScraper()
        .then(report => {
            console.log('🎯 Scraping completo finalizado exitosamente');
            process.exit(0);
        })
        .catch(error => {
            console.error('💥 Error fatal:', error);
            process.exit(1);
        });
}

module.exports = { ProductionStreamingScraperComplete, runCompleteProductionScraper };
