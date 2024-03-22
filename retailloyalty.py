"""
Парсер плагина SPP

1/2 документ плагина
"""
import logging
import time
from datetime import datetime

import dateparser
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from src.spp.types import SPP_document


class RetailLoyalty:
    """
    Класс парсера плагина SPP

    :warning Все необходимое для работы парсера должно находится внутри этого класса

    :_content_document: Это список объектов документа. При старте класса этот список должен обнулиться,
                        а затем по мере обработки источника - заполняться.


    """

    SOURCE_NAME = 'retailloyalty'
    HOST = 'https://retail-loyalty.org/news/'
    url_template = f'{HOST}/research/index.htm?bis_fsi_publs_page='
    date_begin = datetime(2019, 1, 1)

    _content_document: list[SPP_document]

    def __init__(self, webdriver, max_count_documents: int = None, last_document: SPP_document = None, *args, **kwargs):
        """
        Конструктор класса парсера

        По умолчанию внего ничего не передается, но если требуется (например: driver селениума), то нужно будет
        заполнить конфигурацию
        """
        # Обнуление списка
        self._content_document = []

        # Webdriver Selenium для парсера
        self._driver = webdriver
        self._max_count_documents = max_count_documents
        self._last_document = last_document

        # Логер должен подключаться так. Вся настройка лежит на платформе
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug(f"Parser class init completed")
        self.logger.info(f"Set source: {self.SOURCE_NAME}")
        ...

    def content(self) -> list[SPP_document]:
        """
        Главный метод парсера. Его будет вызывать платформа. Он вызывает метод _parse и возвращает список документов
        :return:
        :rtype:
        """
        self.logger.debug("Parse process start")
        try:
            self._parse()
        except Exception as e:
            self.logger.debug(f'Parsing stopped with error: {e}')
        else:
            self.logger.debug("Parse process finished")
        return self._content_document

    def _parse(self):
        """
        Метод, занимающийся парсингом. Он добавляет в _content_document документы, которые получилось обработать
        :return:
        :rtype:
        """
        # HOST - это главная ссылка на источник, по которому будет "бегать" парсер
        self.logger.debug(F"Parser enter to {self.HOST}")

        # ========================================
        # Тут должен находится блок кода, отвечающий за парсинг конкретного источника
        # -
        for url in self._encounter_pages():
            # Получение новой страницы с новостями
            links = self._collect_doc_links(url)  # выборка всех ссылок на новости из страницы
            for link in links:
                self._parse_page(link)

        ...

    def _collect_doc_links(self, url) -> list:
        self._initial_access_source(url)
        self.logger.debug(f'Start collect publications from {url}')

        links = []

        try:
            news = self._driver.find_elements(By.CLASS_NAME, 'news-item')
            for new in news:
                text_block = WebDriverWait(new, 2).until(ec.presence_of_element_located((By.CLASS_NAME, 'text-block')))
                el = WebDriverWait(text_block, 2).until(ec.presence_of_element_located((By.XPATH, 'a[1]')))
                links.append(str(el.get_attribute('href')))
        except Exception as e:
            self.logger.error(e)

        return links

    def _encounter_pages(self) -> str:
        _base = "https://retail-loyalty.org/news/"
        _params = '?PAGEN_1='
        page = 1
        while True:
            url = _base + _params + str(page)
            page += 1
            yield url

    def _parse_page(self, url) -> SPP_document:
        self.logger.debug(f'Start parse news at {url}')

        try:
            self._initial_access_source(url, 4)

            _article = WebDriverWait(self._driver, 2).until(
                ec.presence_of_element_located((By.CLASS_NAME, 'news-article')))
            _title = WebDriverWait(_article, 2).until(
                ec.presence_of_element_located((By.CLASS_NAME, 'page-header'))).text
            _weblink = url
            _date = WebDriverWait(_article, 2).until(
                ec.presence_of_element_located((By.CLASS_NAME, 'news-line-date'))).text
            _time = WebDriverWait(_article, 2).until(
                ec.presence_of_element_located((By.CLASS_NAME, 'news-line-time'))).text

            _published = dateparser.parse(_date + _time)

        except Exception as e:
            raise NoSuchElementException(
                'Страница новости не открывается или ошибка получения обязательных полей') from e
        else:
            doc = SPP_document(
                None,
                _title,
                None,
                None,
                _weblink,
                None,
                None,
                _published,
                None,
            )

            _text = WebDriverWait(_article, 2).until(ec.presence_of_element_located((By.ID, 'article'))).text
            doc.text = _text
            try:
                _abstract = WebDriverWait(_article, 2).until(ec.presence_of_element_located((By.ID, 'news-line-preview'))).text
                doc.abstract = _abstract
            except:
                self.logger.debug('There aren\'t a abstract in the article')

            _others = {}
            try:
                _tag_el = _article.find_element(By.CLASS_NAME, 'line-tags')
                _tags = []
                for _tag in _tag_el.find_elements(By.CLASS_NAME, 'rubrics-name'):
                    _span = _tag.find_element(By.TAG_NAME, 'span')
                    _tags.append(_tag.text.replace(_span.text, ''))
                _others['tags'] = tuple(_tags)
            except:
                self.logger.debug('There aren\'t a tags in the article')

            try:
                _rubric_els = _article.find_element(By.CLASS_NAME, 'line-rubrics')
                _rubrics = []
                for _rubric in _rubric_els.find_elements(By.CLASS_NAME, 'rubrics-name'):
                    _span = _rubric.find_element(By.TAG_NAME, 'span')
                    _rubrics.append(_rubric.text.replace(_span.text, ''))
                _others['rubrics'] = tuple(_rubrics)
            except:
                self.logger.debug('There aren\'t a rubrics in the article')

            doc.other_data = _others
            self.find_document(doc)

    def _initial_access_source(self, url: str, delay: int = 2):
        self._driver.get(url)
        self.logger.debug('Entered on web page ' + url)
        time.sleep(delay)
        self._agree_cookie_pass()

    def _agree_cookie_pass(self):
        """
        Метод прожимает кнопку agree на модальном окне
        """
        cookie_agree_xpath = '//*[@id="onetrust-accept-btn-handler"]'

        try:
            cookie_button = self._driver.find_element(By.XPATH, cookie_agree_xpath)
            if WebDriverWait(self._driver, 5).until(ec.element_to_be_clickable(cookie_button)):
                cookie_button.click()
                self.logger.debug(F"Parser pass cookie modal on page: {self._driver.current_url}")
        except NoSuchElementException as e:
            self.logger.debug(f'modal agree not found on page: {self._driver.current_url}')

    @staticmethod
    def _find_document_text_for_logger(doc: SPP_document):
        """
        Единый для всех парсеров метод, который подготовит на основе SPP_document строку для логера
        :param doc: Документ, полученный парсером во время своей работы
        :type doc:
        :return: Строка для логера на основе документа
        :rtype:
        """
        return f"Find document | name: {doc.title} | link to web: {doc.web_link} | publication date: {doc.pub_date}"

    def find_document(self, _doc: SPP_document):
        """
        Метод для обработки найденного документа источника
        """
        if self._last_document and self._last_document.hash == _doc.hash:
            raise OverflowError(f"Find already existing document ({self._last_document})")

        self._content_document.append(_doc)
        self.logger.info(self._find_document_text_for_logger(_doc))

        if self._max_count_documents and len(self._content_document) >= self._max_count_documents:
            raise OverflowError(f"Max count articles reached ({self._max_count_documents})")
