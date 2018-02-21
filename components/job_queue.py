from enum import Enum
from time import sleep

from PyQt5 import QtCore

import socialreaper


class QueueState(Enum):
    RUNNING = "running"
    STOPPED = "stopped"


class JobState(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    QUEUED = "queued"
    SAVING = "saving"
    FINISHED = "finished"


class Job():
    def __init__(self, outputPath, sourceName, sourceFunction, functionArgs, sourceKeys, job_update):
        self.iterator = eval(
            "socialreaper.{}(**{}).{}({})".format(sourceName, sourceKeys, sourceFunction, functionArgs))
        self.outputPath = outputPath
        self.sourceName = sourceName
        self.sourceFunction = sourceFunction
        self.functionArgs = functionArgs
        self.sourceKeys = sourceKeys

        self.state = JobState.STOPPED
        self.job_update = job_update
        self.data = []
        self.flat_data = []
        self.keys = set()
        self.flat_keys = set()

    def add_data(self, data):
        self.data.append(data)
        flat_data = socialreaper.tools.flatten(data)
        self.flat_data.append(flat_data)

        keys = data.keys()
        if keys != self.keys:
            self.keys.update(keys)

        flat_keys = flat_data.keys()
        if flat_keys != self.flat_keys:
            self.flat_keys.update(flat_keys)

    def inc_data(self):
        self.state = JobState.RUNNING
        try:
            value = self.iterator.__next__()
            self.add_data(value)
            self.job_update.emit(self)
            return value
        except StopIteration:
            return self.end_job()
        except socialreaper.IterError as e:
            print("Job Failed")
            print(e)
            return self.end_job()

    def end_job(self):
        # Save CSV
        self.state = JobState.SAVING
        self.job_update.emit(self)
        print("Saving job")
        socialreaper.tools.to_csv(self.flat_data, filename=self.outputPath, flat=False)
        self.state = JobState.FINISHED
        self.job_update.emit(self)
        return False

    def send_update(self):
        if self.state == JobState.RUNNING:
            if self.iterator.total % 20:
                self.job_update.emit(self)
            else:
                return

        self.job_update.emit(self)


class Queue(QtCore.QThread):
    job_update = QtCore.pyqtSignal(Job)
    queue_update = QtCore.pyqtSignal(list)
    queue_selected = QtCore.pyqtSignal(list)

    def __init__(self, window):
        super().__init__()

        self.state = QueueState.STOPPED

        self.window = window
        self.jobs = []

        self.currentJobState = None

        self.start()
        self.add_actions()

    def add_actions(self):
        self.window.queueStart.clicked.connect(self.start_queue)
        self.window.queueStop.clicked.connect(self.stop)
        self.window.queueClear.clicked.connect(self.clear)
        self.window.queueUp.clicked.connect(self.up)
        self.window.queueDown.clicked.connect(self.down)
        self.window.queueRemove.clicked.connect(self.remove)

    def start_queue(self):
        for job in self.jobs:
            job.state = JobState.QUEUED
        self.state = QueueState.RUNNING

    def stop(self):
        self.state = QueueState.STOPPED
        for job in self.jobs:
            job.state = JobState.STOPPED
        self.queue_update.emit(self.jobs)


    def clear(self):
        self.jobs.clear()
        self.queue_update.emit(self.jobs)

    def up(self):
        indexes = self.window.queue_table.selected_jobs()
        for i, index in enumerate(indexes):
            if index > 0:
                self.jobs.insert(index - 1, self.jobs.pop(index))
                indexes[i] = indexes[i] - 1
        self.queue_update.emit(self.jobs)
        self.queue_selected.emit(indexes)

    def down(self):
        indexes = self.window.queue_table.selected_jobs()
        for i, index in enumerate(indexes):
            if index < len(self.jobs) - 1:
                self.jobs.insert(index + 1, self.jobs.pop(index))
                indexes[i] = indexes[i] + 1
        self.queue_update.emit(self.jobs)
        self.queue_selected.emit(indexes)

    def remove(self):
        indexes = self.window.queue_table.selected_jobs()
        for index in indexes:
            self.jobs.pop(index)
        self.queue_update.emit(self.jobs)
        self.queue_selected.emit(indexes)

    def add_jobs(self, details):
        try:
            for params in details:
                self.jobs.append(Job(*params, self.job_update))
        except Exception as e:
            print(f"Error occurred adding iterator\n{e}")

        self.queue_update.emit(self.jobs)

    def test(self):
        print("Hello")

    def run(self):
        while True:
            if self.state == QueueState.RUNNING:
                self.inc_job()
            elif self.state == QueueState.STOPPED:
                sleep(1)

    def inc_job(self):
        if len(self.jobs) > 0:
            value = self.jobs[0].inc_data()

            if value:
                # self.display_value(value)
                currentJobState = self.jobs[0].state
                if self.currentJobState != currentJobState:
                    self.currentJobState = currentJobState
                    self.queue_update.emit(self.jobs)
            else:
                self.jobs.pop(0)
                self.queue_update.emit(self.jobs)


        else:
            self.state = QueueState.STOPPED
            self.queue_update.emit(self.jobs)

    def display_value(self, value):
        print(value)


class IterateData(QtCore.QThread):
    item_generated = QtCore.pyqtSignal(dict)
    progress_changed = QtCore.pyqtSignal(int)
    api_error = QtCore.pyqtSignal(Exception)

    def __init__(self, iterator):
        super().__init__()

        self.iterator = iterator

    def run(self):
        for count, item in enumerate(self.iterator):
            print(item)
